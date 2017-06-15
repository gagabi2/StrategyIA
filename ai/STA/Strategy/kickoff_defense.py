# Under MIT license, see LICENSE.txt
from functools import partial

from RULEngine.Util.Pose import Pose
from RULEngine.Util.Position import Position
from ai.STA.Tactic.Stop import Stop
from ai.STA.Tactic.goToPositionPathfinder import GoToPositionPathfinder
from ai.STA.Tactic.tactic_constants import Flags
from ai.states.game_state import GameState
from . Strategy import Strategy



class KickOffDefense(Strategy):
    def __init__(self, p_game_state: GameState):
        super().__init__(p_game_state)
        front_left = self.game_state.my_team.available_players[3]
        front_right = self.game_state.my_team.available_players[0]
        middle = self.game_state.my_team.available_players[1]
        back_right = self.game_state.my_team.available_players[2]
        back_left = self.game_state.my_team.available_players[4]
        goalkeeper = self.game_state.my_team.available_players[5]

        # Positions objectifs des joueurs
        front_left_position = Pose(Position(self.game_state.field.constant["FIELD_X_LEFT"] / 15,
                                             self.game_state.field.constant["FIELD_Y_BOTTOM"] / 2.1))
        front_right_position = Pose(Position(self.game_state.field.constant["FIELD_X_LEFT"] / 15,
                                              self.game_state.field.constant["FIELD_Y_TOP"] / 2.1))
        middle_position = Pose(Position(self.game_state.field.constant["FIELD_X_LEFT"] / 2.5, 0))
        back_right_position = Pose(Position(self.game_state.field.constant["FIELD_X_LEFT"] / 1.5,
                                               self.game_state.field.constant["FIELD_Y_BOTTOM"] * 3/5))
        back_left_position = Pose(Position(self.game_state.field.constant["FIELD_X_LEFT"] / 1.5,
                                              self.game_state.field.constant["FIELD_Y_TOP"] * 3/5))
        goalkeeper_position = Pose(Position(self.game_state.field.constant["FIELD_X_LEFT"] * 9 / 10, 0))

        print(self.game_state.field.constant["FIELD_X_LEFT"])

        self.add_tactic(front_right.id, GoToPositionPathfinder(self.game_state, front_right,  front_right_position))
        self.add_tactic(front_right.id, Stop(self.game_state, front_right))
        self.add_condition(front_right.id, 0, 1, partial(self.condition, front_right))

        self.add_tactic(front_left.id, GoToPositionPathfinder(self.game_state, front_left, front_left_position))
        self.add_tactic(front_left.id, Stop(self.game_state, front_left))
        self.add_condition(front_left.id, 0, 1, partial(self.condition, front_left))

        self.add_tactic(middle.id, GoToPositionPathfinder(self.game_state, middle, middle_position))
        self.add_tactic(middle.id, Stop(self.game_state, middle))
        self.add_condition(middle.id, 0, 1, partial(self.condition, middle))

        self.add_tactic(back_right.id,
                        GoToPositionPathfinder(self.game_state, back_right, back_right_position))
        self.add_tactic(back_right.id, Stop(self.game_state, back_right))
        self.add_condition(back_right.id, 0, 1, partial(self.condition, back_right))

        self.add_tactic(back_left.id, GoToPositionPathfinder(self.game_state, back_left, back_left_position))
        self.add_tactic(back_left.id, Stop(self.game_state, back_left))
        self.add_condition(back_left.id, 0, 1, partial(self.condition, back_left))

        self.add_tactic(goalkeeper.id, GoToPositionPathfinder(self.game_state, goalkeeper, goalkeeper_position))
        self.add_tactic(goalkeeper.id, Stop(self.game_state, goalkeeper))
        self.add_condition(goalkeeper.id, 0, 1, partial(self.condition, goalkeeper))

    def condition(self, i):
        # print(i, self.graphs[i].get_current_tactic().status_flag == Flags.SUCCESS)
        return self.graphs[i.id].get_current_tactic().status_flag == Flags.SUCCESS