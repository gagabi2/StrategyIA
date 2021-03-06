# Under MIT licence, see LICENCE.txt
from typing import List
import numpy as np

from RULEngine.Debug.debug_interface import DebugInterface
from RULEngine.Game.OurPlayer import OurPlayer
from RULEngine.Util.Pose import Pose
from RULEngine.Util.constant import BALL_RADIUS, ROBOT_RADIUS
from ai.STA.Action.AllStar import AllStar
from ai.STA.Tactic.Tactic import Tactic
from ai.STA.Tactic.tactic_constants import Flags
from ai.Util.ai_command import AICommandType
from ai.states.game_state import GameState

__author__ = 'RoboCupULaval'

ORIENTATION_DEADZONE = 0.2
DISTANCE_TO_KICK_REAL = ROBOT_RADIUS * 3.4
DISTANCE_TO_KICK_SIM = ROBOT_RADIUS + BALL_RADIUS
COMMAND_DELAY = 1.5


class PositionForPass(Tactic):
    """
    méthodes:
        exec(self) : Exécute une Action selon l'état courant
    attributs:
        game_state: L'état courant du jeu.
        player: Instance du joueur auquel est assigné la tactique
        current_state : L'état courant de la tactique
        next_state : L'état suivant de la tactique
        status_flag : L'indicateur de progression de la tactique
        target: Position à laquelle faire face après avoir pris la balle
    """

    def __init__(self, game_state: GameState, player: OurPlayer, target: Pose=Pose(), args: List[str]=None):
        Tactic.__init__(self, game_state, player, target, args)
        self.current_state = self.move_to_pass_position
        self.next_state = self.move_to_pass_position

    def move_to_pass_position(self):
        self.next_state = self.move_to_pass_position
        if self._is_player_towards_ball():
            self.status_flag = Flags.SUCCESS
        else:
            self.status_flag = Flags.WIP
        return AllStar(self.game_state, self.player, **{"pose_goal": self._get_destination_pose(),
                                                        "ai_command_type": AICommandType.MOVE})

    def _is_player_towards_ball(self, fact=-0.99):
        player_x = self.player.pose.position.x
        player_y = self.player.pose.position.y
        ball_x = self.game_state.get_ball_position().x
        ball_y = self.game_state.get_ball_position().y

        vector_ball_2_player = np.array([player_x - ball_x, player_y - ball_y])
        vector_ball_2_player /= np.linalg.norm(vector_ball_2_player)
        vector_player_dir = np.array([np.cos(self.player.pose.orientation),
                                      np.sin(self.player.pose.orientation)])
        if np.dot(vector_ball_2_player, vector_player_dir) < fact:
            return True
        return False

    def _get_destination_pose(self):
        player_x = self.player.pose.position.x
        player_y = self.player.pose.position.y
        ball_x = self.game_state.get_ball_position().x
        ball_y = self.game_state.get_ball_position().y

        destination_orientation = np.arctan2(ball_y - player_y, ball_x - player_x)
        return Pose(self.target.position, destination_orientation)
