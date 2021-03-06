from typing import List

from RULEngine.Game.OurPlayer import OurPlayer
from RULEngine.Util.Pose import Pose
from RULEngine.Util.Position import Position
from RULEngine.Util.geometry import get_distance, conv_position_2_list, remove_duplicates
from ai.Algorithm.IntelligentModule import Pathfinder
from ai.states.world_state import WorldState
import numpy as np


class Path:
    def __init__(self, start=Position(),  end=Position()):

        self.start = start
        self.goal = end
        self.points = [start, end]
        self.speeds = [0, 0]

    def join_segments(self, other):
        new_path = Path()
        new_path.points = self.points+other.points[1:]
        new_path.start = self.start
        new_path.goal = other.points[-1]
        return new_path

    def split_path(self, idx):
        if idx < 1:
            path_1 = Path()
            path_2 = self
        else:
            path_1 = Path()
            path_1.start = self.start
            path_1.goal = self.points[idx]
            path_1.points = self.points[:idx+1]
            path_2 = Path()
            path_2.start = self.points[idx]
            path_2.goal = self.goal
            path_2.points = self.points[idx:]
        return path_1, path_2

    @staticmethod
    def generate_path_from_points(points_list, speed_list=None, threshold=None):

        if speed_list is None:
            speed_list = [0, 0]
        if len(points_list) < 3:
            pass
        else:
            if (threshold is not None) and len(speed_list) > 2:
                if np.linalg.norm(points_list[0] - points_list[1]) < threshold:
                    del points_list[1]
                    del speed_list[1]
                # print(position_list)
                # print(new_speed_list)

        #points étant une liste de positions
        new_path = Path()
        new_path.start = points_list[0]
        new_path.goal = points_list[-1]
        new_path.points = points_list
        new_path.speeds = speed_list

        return new_path

    def get_path_length(self):
        length = 0
        for idx, point in enumerate(self.points[:-1]):
            length += np.linalg.norm(point - self.points[idx+1])
        return length

    def quick_update_path(self, player):
        self.points[0] = player.pose.position
        return self.generate_path_from_points(self.points, self.speeds, 80)


class PathPartitionner(Pathfinder):
    def __init__(self, p_worldstate: WorldState):
        super().__init__(p_worldstate)
        self.p_worldstate = p_worldstate
        self.game_state = self.p_worldstate.game_state
        self.path = Path(Position(0, 0), Position(0, 0))
        self.raw_path = Path(Position(0, 0), Position(0, 0))
        self.res = 100
        self.gap_proxy = 200
        self.max_recurs = 5
        self.players_obstacles = []
        self.pose_obstacle = None
        self.reshaper = PathReshaper(self.path)
        self.cruise_speed = 1
        self.player = None
        self.closest_obs_speed = np.array([0, 0])

    def fastpathplanner(self, path, depth=0, avoid_dir=None):

        if self.is_path_collide(path) and depth < self.max_recurs:

            sub_target, avoid_dir = self.search_point(path, avoid_dir)
            #print(sub_target)
            path_1 = Path(path.start, sub_target)

            path_1 = self.fastpathplanner(path_1, depth + 1, avoid_dir)

            path_2 = Path(sub_target, path.goal)
            path_2 = self.fastpathplanner(path_2, depth + 1, avoid_dir)

            path = path_1.join_segments(path_2)

        return path

    def get_path(self, player: OurPlayer, pose_target: Pose=Pose(), cruise_speed: [int, float]=1,
                 old_path=None, old_raw_path=Path(Position(99999, 99999), Position(99999, -99999))):
        self.cruise_speed = cruise_speed
        self.player = player

        i = 0

        self.pose_obstacle = np.zeros((len(self.game_state.my_team.available_players) +
                                       len(self.game_state.other_team.available_players) - 1, 2))

        for player in self.game_state.my_team.available_players.values():
            if player.id != self.player.id:
                self.pose_obstacle[i, :] = player.pose.position
                self.players_obstacles.append(player)
                i += 1
        for player in self.game_state.other_team.available_players.values():
            self.pose_obstacle[i, :] = player.pose.position
            self.players_obstacles.append(player)
            i += 1

        # tentative de code pour ne pas recalculer le path a toutes les ittérations (marche un peu mais pas parfait)
        #if (old_path is not None) and (np.linalg.norm(self.path.goal - old_raw_path.goal) < 20):
        if (old_path is not None) and (not self.is_path_collide(old_raw_path, tolerance=self.gap_proxy-50)) and \
                (np.linalg.norm(self.path.goal - old_raw_path.goal) < 20):
            old_raw_path.quick_update_path(self.player)
            old_path.quick_update_path(self.player)
            self.path = old_path
            self.raw_path = old_raw_path
            self.path = self.remove_redundant_points()

        else:
            self.path = Path(self.player.pose.position, pose_target.position)
            if self.path.get_path_length() < 1:
                """
                hack shady pour eviter une erreur shady (trop fatiguer pour dealer ak ste shit la)
                
                File "/home/phil/robocup/StrategyIA/RULEngine/Util/Position.py", line 68, in __eq__
                    min_abs_tol = min(self.abs_tol, other.position.abs_tol)
                    AttributeError: 'numpy.ndarray' object has no attribute 'position'
                """
                return self.path , self.path
            self.closest_obs_speed = self.find_closest_obstacle(self.player.pose.position, self.path)
            self.path = self.fastpathplanner(self.path)


            self.raw_path = self.path
            self.path = self.reshaper.reshape_path(self.path, self.player, self.cruise_speed)
            self.path = self.remove_redundant_points()

        # print("points", self.path.points)
        # print("speeds", self.path.speeds)
        return self.path, self.raw_path

    def get_raw_path(self, pose_target=Pose()):
        # sans path_reshaper
        i = 0

        self.pose_obstacle = np.zeros((len(self.game_state.my_team.available_players) +
                                       len(self.game_state.other_team.available_players) - 1, 2))
        for player in self.game_state.my_team.available_players.values():
            if player.id != self.player.id:
                self.pose_obstacle[i, :] = player.pose.position
                self.players_obstacles.append(player)
                i += 1
        for player in self.game_state.other_team.available_players.values():
            self.pose_obstacle[i, :] = player.pose.position
            self.players_obstacles.append(player)
            i += 1

        self.path = Path(self.player.pose.position, pose_target.position)

        return self.fastpathplanner(self.path)

    def is_path_collide(self, path, obstacles=None, tolerance=None):
        if obstacles is None:
            obstacles = self.pose_obstacle
        if tolerance is None:
            tolerance = self.gap_proxy
        for idx, points in enumerate(path.points[:-1]):
            pose_start = path.points[idx]
            pose_target = path.points[idx + 1]
            direction = (pose_target - pose_start)
            if np.linalg.norm(direction) < 0.00001:
                return False
            else:
                direction = direction / np.linalg.norm(direction)
            distance_sub_path = np.linalg.norm(pose_start - pose_target)
            if distance_sub_path > 0.01:
                for pose_obs in obstacles:
                    vec_robot_2_obs = pose_obs - pose_start
                    dist_from_path = np.linalg.norm(np.cross(direction, vec_robot_2_obs))
                    projection_obs_on_direction = \
                        np.dot(direction, vec_robot_2_obs / np.linalg.norm(vec_robot_2_obs))
                    if projection_obs_on_direction < 0.00001 or projection_obs_on_direction > 1:
                        #le vecteur entre l'obstacle et la ligne n'est pas perpendiculaire
                        dist_from_path_temp = np.linalg.norm(pose_start - pose_obs)
                        if dist_from_path_temp > np.linalg.norm(pose_target - pose_obs):
                            dist_from_path = np.linalg.norm(pose_target - pose_obs)
                        else:
                            dist_from_path = dist_from_path_temp
                    if tolerance > dist_from_path:
                        return True
        return False

    def find_closest_obstacle(self, point, path):

        dist_point_obs = np.inf
        closest_obs = None
        closest_player = self.players_obstacles[0].pose.position
        #print(get_distance(path.start, path.goal))
        if np.linalg.norm(path.start - path.goal) < 0.001:
            return [closest_obs, dist_point_obs, closest_player]
        if point == path.start:
            return [closest_obs, dist_point_obs, closest_player]
        pose_start = path.start
        direction = (point - pose_start) / np.linalg.norm(point - pose_start)

        for idx, pose_obs in enumerate(self.pose_obstacle):
            vec_robot_2_obs_temp = pose_obs - pose_start
            dist_from_path_temp = np.linalg.norm(np.cross(direction, vec_robot_2_obs_temp))
            if self.gap_proxy > dist_from_path_temp and self.is_path_collide(path, [pose_obs]):
                obstacle_pos = Position(pose_obs)
                dist = (path.start - obstacle_pos).norm()
                if dist < dist_point_obs:
                    dist_point_obs = dist
                    closest_obs = obstacle_pos
                    closest_player = self.players_obstacles[idx]
        return [closest_obs, dist_point_obs, closest_player]

    def verify_sub_target(self, sub_target):
        for pose_obs in self.pose_obstacle:
            dist_sub_2_obs = (Position(pose_obs) - sub_target).norm()
            if dist_sub_2_obs < self.gap_proxy:
                return True
        return False

    def search_point(self, path, avoid_dir=None):

        pose_robot = path.start
        #print(pose_robot)
        pose_target = path.goal
        pose_obstacle_closest, dist_point_obs, closest_player = self.find_closest_obstacle(pose_target, path)
        if pose_obstacle_closest is None:
            sub_target = pose_target
            return sub_target

        direction = (pose_target - pose_robot) / np.linalg.norm(pose_target - pose_robot)
        vec_robot_2_obs = np.array(conv_position_2_list(pose_obstacle_closest - pose_robot))
        len_along_path = np.dot(vec_robot_2_obs, direction)
        dist_from_path = np.linalg.norm(np.cross(direction, vec_robot_2_obs))
        projection_obs_on_direction = np.dot(direction, vec_robot_2_obs / np.linalg.norm(vec_robot_2_obs))
        if 0 < len_along_path < (pose_target - pose_robot).norm():
            vec_perp = np.cross(np.append(direction, [0]), np.array([0, 0, 1]))
            vec_perp = vec_perp[0:2] / np.linalg.norm(vec_perp)
            # print(self.player.velocity)
            cruise_speed = self.player.velocity.position
            self.closest_obs_speed = closest_player.velocity.position
            avoid_dir = -vec_perp

            if avoid_dir is None:
                avoid_dir = -vec_perp
                sub_target_1 = np.array(conv_position_2_list(pose_robot)) + \
                    direction * len_along_path + vec_perp * self.res
                sub_target_2 = np.array(conv_position_2_list(pose_robot)) + \
                    direction * len_along_path - vec_perp * self.res
                bool_sub_target_1 = self.verify_sub_target(Position(sub_target_1[0], sub_target_1[1]))
                bool_sub_target_2 = self.verify_sub_target(Position(sub_target_2[0], sub_target_2[1]))

                while bool_sub_target_1:
                    sub_target_1 += vec_perp * self.res
                    bool_sub_target_1 = self.verify_sub_target(Position(sub_target_1[0], sub_target_1[1]))

                sub_target_1 += vec_perp * 0.01 * self.res
                while bool_sub_target_2:

                    sub_target_2 -= vec_perp * self.res
                    bool_sub_target_2 = self.verify_sub_target(Position(sub_target_2[0], sub_target_2[1]))

                sub_target_2 -= vec_perp * 0.01 * self.res
                if np.linalg.norm(cruise_speed) < 0.1:
                    sub_target = sub_target_1
                elif np.abs(np.dot(direction, (sub_target_1 - path.start) /
                         np.linalg.norm(sub_target_1 - path.start))) > \
                        np.abs(np.dot(direction, (sub_target_2 - path.start) /
                            np.linalg.norm(sub_target_2 - path.start))):
                    sub_target = sub_target_1
                else:
                    sub_target = sub_target_2

            else:
                # if np.dot(avoid_dir, np.transpose(vec_perp)) < 0:
                #     vec_perp = -vec_perp
                if np.linalg.norm(avoid_dir) > 0.001:
                    avoid_dir /= np.linalg.norm(avoid_dir)
                elif np.dot(avoid_dir, np.transpose(vec_perp)) < 0:
                    avoid_dir = -vec_perp
                else:
                    avoid_dir = vec_perp
                sub_target = np.array(conv_position_2_list(pose_robot)) +\
                    direction * len_along_path + vec_perp * self.res

                bool_sub_target = self.verify_sub_target(Position(sub_target[0], sub_target[1]))
                while bool_sub_target:
                    sub_target -= avoid_dir * self.res
                    bool_sub_target = self.verify_sub_target(Position(sub_target[0], sub_target[1]))

                sub_target -= avoid_dir * 0.01 * self.res
                avoid_dir = vec_perp
            sub_target = Position(sub_target[0], sub_target[1])
        else:
            sub_target = pose_target
        return [sub_target, avoid_dir]

    def get_next_point(self, robot_id=None):
        pass

    def update(self):
        pass

    def remove_redundant_points(self):
        if len(self.path.points) > 2:
            points, speeds = remove_duplicates(self.path.points, self.path.speeds, 5)
            return Path().generate_path_from_points(points, speeds)
        else:
            return Path().generate_path_from_points(self.path.points, self.path.speeds)


class PathReshaper:
    def __init__(self, path: Path):
        self.path = path
        self.dist_from_path = 25  # mm
        self.player_id = None
        self.player = None
        self.vel_max = None

    def reshape_path(self, path: Path, player: OurPlayer, vel_cruise: [int, float]=1000):
        self.path = path
        self.player = player
        cmd = self.player.ai_command
        if cmd.cruise_speed:
            vel_cruise = cmd.cruise_speed * 1000
        # print(vel_cruise)
        self.vel_max = vel_cruise
        positions_list = [path.points[0]]
        for idx, point in enumerate(path.points[1:-1]):
            i = idx + 1
            if np.linalg.norm(path.points[i] - path.points[i+1]) < 10:
                continue
            positions_list += [path.points[i]]
        positions_list += [path.points[-1]]
        self.path.points = positions_list
        p1 = self.path.points[0]
        point_list = [p1]
        speed_list = [0]

        for idx, point in enumerate(self.path.points[1:-1]):
            self.dist_from_path = 50  # mm
            i = idx + 1
            p2 = point
            p3 = self.path.points[i+1]
            # if np.linalg.norm(p1, p2) / 2 < OurPlayer.max_acc * 2 / vel_cruise ** 2:
            #     # on ne calcul pas le radius a partir de vel cruise. profil triangulaire
            #     vel_pointe = np.sqrt(2 * OurPlayer.max_acc / (np.linalg.norm(p1,p2) / 2))
            #     radius_at_const_speed = vel_pointe ** 2 / (OurPlayer.max_acc * 1000)
            # else:
            radius_at_const_speed = vel_cruise ** 2 / (OurPlayer.max_acc * 1000)
            theta = abs(np.math.atan2(p3[1]-p2[1], p3[0]-p2[0]) - np.math.atan2(p1[1]-p2[1], p1[0]-p2[0]))
            try:
                dist_deviation = (radius_at_const_speed/(np.math.sin(theta/2)))-radius_at_const_speed
            except ZeroDivisionError:
                dist_deviation = 0
            speed = vel_cruise
            radius = radius_at_const_speed
            while dist_deviation > self.dist_from_path:
                speed *= 0.4
                radius = speed ** 2 / (OurPlayer.max_acc * 1000)
                dist_deviation = (radius / (np.math.sin(theta / 2))) - radius
            # print(radius, radius_at_const_speed)
            if np.linalg.norm(p1-p2) < 0.001 or np.linalg.norm(p2-p3) < 0.001 or np.linalg.norm(p1-p3) < 0.001:
                # on traite tout le cas ou le problème dégènere
                point_list += [p2]
                speed_list += [vel_cruise]
            else:
                p4 = p2 + np.sqrt(np.square(dist_deviation + radius) - radius ** 2) *\
                          (p1 - p2) / np.linalg.norm(p1 - p2)
                p5 = p2 + np.sqrt(np.square(dist_deviation + radius) - radius ** 2) *\
                    (p3 - p2) / np.linalg.norm(p3 - p2)
                if np.linalg.norm(p4-p5) > np.linalg.norm(p3-p1):
                    point_list += [p2]
                    speed_list += [vel_cruise]
                elif np.linalg.norm(p1 - p2) < np.linalg.norm(p4 - p2):
                    radius *= np.linalg.norm(p1 - p2) / np.linalg.norm(p4 - p2)
                    dist_deviation = (radius / (np.math.sin(theta / 2))) - radius
                    p4 = p2 + np.sqrt(np.square(dist_deviation + radius) - radius ** 2) * (p1 - p2) / np.linalg.norm(
                        p1 - p2)
                    p5 = p2 + np.sqrt(np.square(dist_deviation + radius) - radius ** 2) * (p3 - p2) / np.linalg.norm(
                        p3 - p2)
                    point_list += [p4, p5]
                    speed_list += [speed, speed]
                elif np.linalg.norm(p3 - p2) < np.linalg.norm(p5 - p2):
                    radius *= np.linalg.norm(p3 - p2) / np.linalg.norm(p5 - p2)
                    dist_deviation = (radius / (np.math.sin(theta / 2))) - radius
                    p4 = p2 + np.sqrt(np.square(dist_deviation + radius) - radius ** 2) * (p1 - p2) / np.linalg.norm(
                        p1 - p2)
                    p5 = p2 + np.sqrt(np.square(dist_deviation + radius) - radius ** 2) * (p3 - p2) / np.linalg.norm(
                        p3 - p2)
                    point_list += [p4, p5]
                    speed_list += [speed, speed]
                else:
                    point_list += [p4, p5]
                    speed_list += [speed, speed]
            # radius = abs(self.dist_from_path*np.sin(theta/2)/(1-np.sin(theta/2)))
            # print(radius, radius_at_const_speed)
            # if radius > radius_at_const_speed:
            #     radius = radius_at_const_speed
            #     self.dist_from_path = -radius + radius / abs(np.math.sin(theta / 2))
            # if np.linalg.norm(p1-p2) < 0.001 or np.linalg.norm(p2-p3) < 0.001 or np.linalg.norm(p1-p3) < 0.001:
            #     # on traite tout le cas ou le problème dégènere
            #     point_list += [point]
            #     speed_list += [vel_cruise/1000]
            # else:
            #     p4 = p2 + np.sqrt(np.square(self.dist_from_path + radius) - radius ** 2) * \
            #          (p1 - p2)/np.linalg.norm(p1-p2)
            #     p5 = p2 + np.sqrt(np.square(self.dist_from_path + radius) - radius ** 2) * \
            #         (p3 - p2) / np.linalg.norm(p3 - p2)
            #     if np.linalg.norm(p4-p5) > np.linalg.norm(p3-p1):
            #         point_list += [point]
            #         speed_list += [vel_cruise/1000]
            #     else:
            #         point_list += [Position.from_np(p4), Position.from_np(p5)]
            #         speed_list += [np.sqrt(radius / (OurPlayer.max_acc * 1000)),
            #                        np.sqrt(radius / (OurPlayer.max_acc * 1000))]
            p1 = point_list[-1]

        speed_list += [0]
        point_list += [self.path.goal]
        # on s'assure que le path est bel et bien réalisable par un robot et on
        # merge les points qui sont trop proches les un des autres.
        position_list = [point_list[0]]
        new_speed_list = [speed_list[0]]
        for idx, point in enumerate(point_list[1:-1]):
            i = idx + 1
            if np.linalg.norm(point_list[i] - point_list[i+1]) < 10:
                continue
            if False:
                min_dist = abs(0.5 * (np.square(speed_list[i]) - np.square(speed_list[i + 1])) / (OurPlayer.max_acc * 1000))
                if min_dist > np.linalg.norm(point_list[i] - point_list[i+1]):
                    if speed_list[i] > speed_list[i + 1]:
                        speed_list[i] *= np.linalg.norm(point_list[i] - point_list[i+1]) / min_dist

            position_list += [point_list[i]]
            new_speed_list += [speed_list[i]]
        position_list += [point_list[-1]]
        new_speed_list += [speed_list[-1]]
        return Path().generate_path_from_points(position_list, new_speed_list)
