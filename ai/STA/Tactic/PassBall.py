# Under MIT licence, see LICENCE.txt
from typing import List

from RULEngine.Game.OurPlayer import OurPlayer
from RULEngine.Util.Pose import Pose
from ai.STA.Tactic.Tactic import Tactic
from ai.STA.Tactic.tactic_constants import Flags
from ai.STA.Action.Kick import Kick
from ai.STA.Action.Idle import Idle
from ai.Util.ball_possession import has_ball_facing_target, has_ball
from ai.states.game_state import GameState

__author__ = 'RoboCupULaval'


class PassBall(Tactic):
    # TODO : vérifier que la balle a été bottée avant de retourner à halt
    """
    méthodes:
        exec(self) : Exécute une Action selon l'état courant
    attributs:
        game_state: L'état courant du jeu.
        player: Instance du joueur auquel est assigné la tactique
        current_state : L'état courant de la tactique
        next_state : L'état suivant de la tactique
        status_flag : L'indicateur de progression de la tactique
        target_position : La position du robot qui reçoit la passe
    """

    def __init__(self, game_state: GameState, player: OurPlayer, target: Pose=Pose(), args: List[str]=None):
        Tactic.__init__(self, game_state, player, target, args)
        # TODO : s'assurer de la target_position soit à l'intérieur du terrain
        self.current_state = self.kick_ball_towards_target
        self.next_state = self.kick_ball_towards_target
        self.target_position = target

    def kick_ball_towards_target(self):
        # check alignment before kicking
        if has_ball_facing_target(self.game_state, self.player.id, self.target_position):
            self.next_state = self.halt
            self.status_flag = Flags.SUCCESS
            return Kick(self.game_state, self.player, 1)
        elif has_ball(self.game_state, self.player.id):
            self.next_state = self.halt
            self.status_flag = Flags.FAILURE
            return Idle(self.game_state, self.player)
        else:  # returns error, strategy goes back to GoGetBall
            self.next_state = self.halt
            self.status_flag = Flags.FAILURE
            return Idle(self.game_state, self.player)
