# Under MIT licence, see LICENCE.txt
import math
from typing import List
import numpy as np
import time

from RULEngine.Game.OurPlayer import OurPlayer
from RULEngine.Util.Pose import Pose
from RULEngine.Util.constant import BALL_RADIUS, ROBOT_RADIUS
from RULEngine.Util.geometry import get_distance
from ai.STA.Action.AllStar import AllStar
from ai.STA.Action.Idle import Idle
from ai.STA.Action.Kick import Kick
from ai.STA.Action.grab import Grab
from ai.STA.Tactic.Tactic import Tactic
from ai.STA.Tactic.tactic_constants import Flags
from ai.Util.ai_command import AICommandType
from ai.STA.Action.GoBehind import GoBehind
from ai.states.game_state import GameState

__author__ = 'RoboCupULaval'

ORIENTATION_DEADZONE = 0.2
DISTANCE_TO_KICK_REAL = ROBOT_RADIUS * 3.4
DISTANCE_TO_KICK_SIM = ROBOT_RADIUS + BALL_RADIUS
COMMAND_DELAY = 1.0


class GoKick(Tactic):
    """
    méthodes:
        exec(self) : Exécute une Action selon l'état courant
    attributs:
        game_state: L'état courant du jeu.
        player : Instance du joueur auquel est assigné la tactique
        current_state : L'état courant de la tactique
        next_state : L'état suivant de la tactique
        status_flag : L'indicateur de progression de la tactique
        target: Position à laquelle faire face après avoir pris la balle
    """

    def __init__(self, game_state: GameState, player: OurPlayer, target: Pose=Pose(), args: List[str]=None):
        Tactic.__init__(self, game_state, player, target, args)
        self.current_state = self.kick_charge
        self.next_state = self.kick_charge
        self.last_time = time.time()
        self.target = target

    def kick_charge(self):
        if time.time() - self.last_time > COMMAND_DELAY:
            self.next_state = self.get_behind_ball
            self.last_time = time.time()

        return AllStar(self.game_state, self.player,  **{"charge_kick": True, "dribbler_on": 1})

    def get_behind_ball(self):
        self.status_flag = Flags.WIP

        player_x = self.player.pose.position.x
        player_y = self.player.pose.position.y

        ball_x = self.game_state.get_ball_position().x
        ball_y = self.game_state.get_ball_position().y

        vector_player_2_ball = np.array([ball_x - player_x, ball_y - player_y])
        vector_player_2_ball /= np.linalg.norm(vector_player_2_ball)

        if self._is_player_towards_ball_and_target():
            self.next_state = self.grab_ball
        else:
            self.next_state = self.get_behind_ball
        return GoBehind(self.game_state, self.player, self.game_state.get_ball_position(),
                        self.target.position, 120, pathfinder_on=True)

    def grab_ball(self):
        if self._get_distance_from_ball() < 120:
            self.next_state = self.kick
            self.last_time = time.time()
        elif self._is_player_towards_ball_and_target(-0.95):
            self.next_state = self.grab_ball
        else:
            self.next_state = self.get_behind_ball
        return Grab(self.game_state, self.player)

    def kick(self):
        if self._get_distance_from_ball() > 1000:
            self.next_state = self.halt
            self.last_time = time.time()
        elif time.time() - self.last_time < COMMAND_DELAY:
            self.next_state = self.kick
        else:
            self.next_state = self.kick_charge
        return Kick(self.game_state, self.player, 1, self.target)

    def halt(self):
        self.status_flag = Flags.SUCCESS
        return Idle(self.game_state, self.player)

    def _get_distance_from_ball(self):
        return get_distance(self.player.pose.position,
                            self.game_state.get_ball_position())

    def _is_player_towards_ball_and_target(self, fact=-0.99):

        player_x = self.player.pose.position.x
        player_y = self.player.pose.position.y

        ball_x = self.game_state.get_ball_position().x
        ball_y = self.game_state.get_ball_position().y

        target_x = self.target.position.x
        target_y = self.target.position.y

        vector_player_2_ball = np.array([ball_x - player_x, ball_y - player_y])
        vector_target_2_ball = np.array([ball_x - target_x, ball_y - target_y])
        vector_player_2_ball /= np.linalg.norm(vector_player_2_ball)
        vector_target_2_ball /= np.linalg.norm(vector_target_2_ball)
        vector_player_dir = np.array([np.cos(self.player.pose.orientation),
                                      np.sin(self.player.pose.orientation)])
        if np.dot(vector_player_2_ball, vector_target_2_ball) < fact:
            if np.dot(vector_player_dir, vector_target_2_ball) < fact:
                return True
        return False

    def _is_player_towards_target(self, fact=-0.99):

        player_x = self.player.pose.position.x
        player_y = self.player.pose.position.y

        target_x = self.target.position.x
        target_y = self.target.position.y

        vector_player_2_target = np.array([player_x - target_x,  player_y - target_y])
        vector_player_2_target /= np.linalg.norm(vector_player_2_target)
        vector_player_dir = np.array([np.cos(self.player.pose.orientation),
                                      np.sin(self.player.pose.orientation)])
        if np.dot(vector_player_dir, vector_player_2_target) < fact:
            return True
        return False

    def _generate_move_to(self):
        player_pose = self.player.pose
        ball_position = self.game_state.get_ball_position()

        dest_position = self.get_behind_ball_position(ball_position)
        destination_pose = Pose(dest_position, player_pose.orientation)

        return AllStar(self.game_state, self.player, **{"pose_goal": destination_pose,
                                                        "ai_command_type": AICommandType.MOVE})

    def get_behind_ball_position(self, ball_position):
        vec_dir = self.target.position - ball_position
        mag = math.sqrt(vec_dir.x ** 2 + vec_dir.y ** 2)
        scale_coeff = ROBOT_RADIUS * 3 / mag
        dest_position = ball_position - (vec_dir * scale_coeff)
        return dest_position
