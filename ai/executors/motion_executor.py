# Under MIT License, see LICENSE.txt
from enum import IntEnum
import numpy as np

from RULEngine.Util.Pose import Pose
from RULEngine.Util.Position import Position
from RULEngine.Util.PID import PID
from ai.Util.ai_command import AICommandType, AIControlLoopType, AICommand
from ai.executors.executor import Executor
from ai.states.world_state import WorldState
from config.config_service import ConfigService


class Pos(IntEnum):
    X = 0
    Y = 1
    THETA = 2


class DotDict(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


class MotionExecutor(Executor):
    def __init__(self, p_world_state: WorldState):
        super().__init__(p_world_state)
        is_simulation = ConfigService().config_dict["GAME"]["type"] == "sim"
        self.robot_motion = [RobotMotion(p_world_state, player_id, is_sim=is_simulation) for player_id in range(12)]

    def exec(self):
        for player in self.ws.game_state.my_team.available_players.values():
            if player.ai_command is None:
                continue

            cmd = player.ai_command
            r_id = player.id

            if cmd.command is AICommandType.MOVE:
                if cmd.control_loop_type is AIControlLoopType.POSITION:
                    cmd.speed = self.robot_motion[r_id].update(cmd)

                elif cmd.control_loop_type is AIControlLoopType.SPEED:
                    speed = fixed2robot(cmd.pose_goal.conv_2_np(), player.pose.orientation)
                    cmd.speed = Pose(Position(speed[Pos.X], speed[Pos.Y]), speed[Pos.THETA])

                elif cmd.control_loop_type is AIControlLoopType.OPEN:
                    cmd.speed = cmd.pose_goal

            elif cmd.command is AICommandType.STOP:
                cmd.speed = Pose(Position(0, 0), 0)
                self.robot_motion[r_id].stop()


class RobotMotion(object):
    def __init__(self, world_state: WorldState, robot_id, is_sim=True):
        self.ws = world_state
        self.id = robot_id

        self.dt = None

        self.setting = get_control_setting(is_sim)
        self.setting.translation.max_acc = None
        self.setting.translation.max_speed = None
        self.setting.rotation.max_speed = None

        self.current_pose = np.zeros(3)
        self.current_orientation = 0
        self.current_velocity = np.zeros(3)
        self.current_acceleration = np.zeros(2)

        self.pose_error = np.zeros(3)
        self.position_error = np.zeros(2)

        self.target_pose = np.zeros(3)
        self.target_speed = np.zeros(1)
        self.target_orientation = np.zeros(1)
        self.target_direction = np.zeros(2)

        self.last_translation_cmd = np.zeros(2)
        self.cruise_speed = np.zeros(1)

        self.next_speed = 0
        self.target_reached = False

        self.x_controller = PID(self.setting.translation.kp,
                                self.setting.translation.ki,
                                self.setting.translation.kd,
                                self.setting.translation.antiwindup)

        self.y_controller = PID(self.setting.translation.kp,
                                self.setting.translation.ki,
                                self.setting.translation.kd,
                                self.setting.translation.antiwindup)

        self.angle_controller = PID(self.setting.rotation.kp,
                                    self.setting.rotation.ki,
                                    self.setting.rotation.kd,
                                    self.setting.rotation.antiwindup)

    def update(self, cmd: AICommand) -> Pose():

        self.update_states(cmd)

        # Rotation control
        rotation_cmd = self.angle_controller.update(self.pose_error[Pos.THETA])
        rotation_cmd = self.apply_rotation_constraints(rotation_cmd)

        # Translation control
        if self.target_reached and self.target_speed <= self.setting.translation.deadzone:
            translation_cmd = np.array([self.x_controller.update(self.pose_error[Pos.X]),
                                        self.y_controller.update(self.pose_error[Pos.Y])])
            self.next_speed = 0
        else:
            translation_cmd = self.get_next_velocity()

        translation_cmd = self.apply_translation_constraints(translation_cmd)

        # Send new command to robot
        translation_cmd = fixed2robot(translation_cmd, self.current_orientation)
        return Pose(Position(translation_cmd[Pos.X], translation_cmd[Pos.Y]), rotation_cmd)

    def get_next_velocity(self) -> np.ndarray:
        """Return the next velocity according to a constant acceleration model of a point mass.
           It try to produce a trapezoidal velocity path with the required cruising and target speed.
           The target speed is the speed that the robot need to reach at the target point."""

        alpha = 1.5
        distance_to_reach_target_speed = 0.5 * (np.square(self.target_speed) - np.square(self.cruise_speed))
        distance_to_reach_target_speed /= self.setting.translation.max_acc
        distance_to_reach_target_speed = alpha * np.abs(distance_to_reach_target_speed)

        self.target_reached = close_to_target(self.position_error[0:2], distance_to_reach_target_speed)

        if self.target_reached:  # We need to go to target speed
            if self.next_speed < self.target_speed:  # Target speed is faster than current speed
                self.next_speed += self.setting.translation.max_acc * self.dt
                if self.next_speed > self.target_speed:  # Next_speed is too fast
                    self.next_speed = self.target_speed
            else:  # Target speed is slower than current speed
                self.next_speed -= self.setting.translation.max_acc * self.dt
        else:  # We need to go to the cruising speed
            if self.next_speed < self.cruise_speed:  # Going faster
                self.next_speed += self.setting.translation.max_acc * self.dt

        self.next_speed = np.clip(self.next_speed, 0, self.cruise_speed)  # We don't want to go faster than cruise speed

        next_velocity = self.next_speed * self.target_direction
        return next_velocity

    def apply_rotation_constraints(self, rotation_cmd: float) -> float:
        rotation_cmd = clamp(rotation_cmd, -self.setting.rotation.max_speed, self.setting.rotation.max_speed)
        if np.abs(rotation_cmd) < self.setting.rotation.sensibility:
            rotation_cmd = 0
        elif np.abs(rotation_cmd) < self.setting.rotation.deadzone:
            rotation_cmd = np.sign(rotation_cmd) * self.setting.rotation.deadzone

        return rotation_cmd

    def apply_translation_constraints(self, translation_cmd: np.ndarray) -> np.ndarray:

        translation_cmd = self.limit_acceleration(translation_cmd)

        translation_cmd = self.limit_speed(translation_cmd)

        if np.abs(translation_cmd[Pos.X]) < self.setting.translation.sensibility:
            translation_cmd[Pos.X] = 0
        elif np.abs(translation_cmd[Pos.X]) < self.setting.translation.deadzone:
            translation_cmd[Pos.X] = np.sign(translation_cmd[Pos.X]) * self.setting.translation.deadzone

        if np.abs(translation_cmd[Pos.Y]) < self.setting.translation.sensibility:
            translation_cmd[Pos.Y] = 0
        elif np.abs(translation_cmd[Pos.Y]) < self.setting.translation.deadzone:
            translation_cmd[Pos.Y] = np.sign(translation_cmd[Pos.Y]) * self.setting.translation.deadzone

        return translation_cmd

    def limit_acceleration(self, translation_cmd: np.ndarray) -> np.ndarray:
        delta_speed = translation_cmd - self.last_translation_cmd
        self.current_acceleration = np.sqrt(np.square(delta_speed).sum()) / self.dt
        self.current_acceleration = clamp(self.current_acceleration, 0, self.setting.translation.max_acc)
        translation_cmd = self.last_translation_cmd + normalized(delta_speed) * self.current_acceleration * self.dt
        self.last_translation_cmd = translation_cmd
        return translation_cmd

    def limit_speed(self, translation_cmd: np.ndarray) ->np.ndarray:
        translation_speed = np.sqrt(np.square(translation_cmd).sum())
        translation_speed = clamp(translation_speed, 0, self.setting.translation.max_speed)
        return translation_speed * normalized(translation_cmd)

    def update_states(self, cmd: AICommand):
        self.dt = self.ws.game_state.game.delta_t

        # Dynamics constraints
        self.setting.translation.max_acc = self.ws.game_state.get_player(self.id).max_acc
        self.setting.translation.max_speed = self.ws.game_state.get_player(self.id).max_speed
        self.setting.rotation.max_speed = self.ws.game_state.get_player(self.id).max_angular_speed

        # Current state of the robot
        self.current_pose = self.ws.game_state.game.friends.players[self.id].pose.conv_2_np()
        self.current_pose = self.current_pose/ np.array([1000, 1000, 1])
        self.current_orientation = self.current_pose[Pos.THETA]
        self.current_velocity = self.ws.game_state.game.friends.players[self.id].velocity
        self.current_velocity.position = self.current_velocity.position / 1000

        # Desired parameters
        if cmd.path:
            self.target_pose = Pose(cmd.path[0], cmd.pose_goal.orientation).conv_2_np()
        else:  # No pathfinder case
            self.target_pose = cmd.pose_goal.conv_2_np()
        self.target_pose = self.target_pose / np.array([1000, 1000, 1])

        self.pose_error = self.target_pose - self.current_pose
        if self.pose_error[Pos.THETA] > np.pi:  # Try to minimize the rotation angle
            self.pose_error[Pos.THETA] = self.pose_error[Pos.THETA] - 2 * np.pi

        self.position_error = self.pose_error[0:2]

        self.target_direction = normalized(self.position_error)
        self.target_speed = cmd.path_speeds[1]/1000
        self.cruise_speed = np.abs(cmd.cruise_speed)

    def stop(self):
        self.angle_controller.reset()
        self.x_controller.reset()
        self.y_controller.reset()
        self.last_translation_cmd = np.zeros(2)
        self.next_speed = 0


def get_control_setting(is_sim: bool):

    if is_sim:
        translation = {"kp": 0.8, "ki": 0.01, "kd": 0, "antiwindup": 20, "deadzone": 0, "sensibility": 0}
        rotation = {"kp": 1, "ki": 0, "kd": 0, "antiwindup": 0, "deadzone": 0, "sensibility": 0}
    else:
        translation = {"kp": 0.8, "ki": 0.01, "kd": 0, "antiwindup": 20, "deadzone": 0.08, "sensibility": 0.02}
        rotation = {"kp": 0.1, "ki": 0.01, "kd": 0, "antiwindup": 10, "deadzone": 0.1, "sensibility": 0.05}

    control_setting = DotDict()
    control_setting.translation = DotDict(translation)
    control_setting.rotation = DotDict(rotation)

    return control_setting

# Geometry functions (Will be in util soon)


def robot2fixed(vector: np.ndarray, angle: float) -> np.ndarray:
    tform = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    return np.dot(tform, vector)


def fixed2robot(vector: np.ndarray, angle: float) -> np.ndarray:
    return robot2fixed(vector, -angle)


def normalized(vector: np.ndarray) -> np.ndarray:
    if np.linalg.norm(vector) > 0:
        return vector / np.linalg.norm(vector)
    else:
        return vector


def orientation(vector: np.ndarray) -> np.ndarray:
    return np.arctan2(vector[1], vector[0])


def close_to_target(pts: np.ndarray, threshold=0.075) -> bool:
    if np.square(pts).sum() <= threshold ** 2:
        return True
    else:
        return False


def clamp(val: float, min_val: float, max_val: float) -> float:
    return max(min(val, max_val), min_val)
