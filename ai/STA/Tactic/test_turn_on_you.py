# Under MIT license, see LICENSE.txt
from typing import List

from RULEngine.Game.OurPlayer import OurPlayer
from RULEngine.Util.Pose import Pose
from ai.states.game_state import GameState
from ai.STA.Tactic.Tactic import Tactic
from ai.STA.Tactic.tactic_constants import Flags
from ai.STA.Action.MoveToPosition import MoveToPosition


class TestTurnOnYou(Tactic):
    def __init__(self, game_state: GameState, player: OurPlayer, target: Pose=Pose(), args: List[str]=None):
        super().__init__(game_state, player, target, args)
        self.next_state = exec

    def exec(self):
        self.status_flag = Flags.WIP
        return MoveToPosition(self.game_state, self.player,
                              self.player.pose, 1)

