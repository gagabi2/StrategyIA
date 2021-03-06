from abc import abstractmethod, ABCMeta

from RULEngine.Game.Referee import RefereeCommand
from ai.Algorithm.IntelligentModule import IntelligentModule


class AutoPlay(IntelligentModule, metaclass=ABCMeta):
    """
        Classe mère des modules de jeu automatique.
        Un module de jeu est un module intelligent servant à faire la sélection
        des stratégies en prenant en compte différents aspects du jeu, notamment le referee
        et la position des robots et de la balle.
    """
    def __init__(self, worldstate):
        super().__init__(worldstate)
        self.selected_strategy = None
        self.current_state = None
        self.next_state = None

    def get_selected_strategy(self):
        return self.selected_strategy

    @property
    def info(self):
        return {
            "selected_strategy": str(self.selected_strategy),
            "current_state": str(self.current_state)
        }

    @abstractmethod
    def update(self):
        """ Effectue la mise à jour du module """
        pass

    @abstractmethod
    def str(self):
        """
            La représentation en string d'un module intelligent devrait
            permettre de facilement envoyer son information dans un fichier de
            log.
        """

        
class SimpleAutoPlay(AutoPlay):
    """
        Classe simple implémentant la sélection de stratégies.
    """
    def __init__(self, worldstate):
        super().__init__(worldstate)
        self.last_ref_command = RefereeCommand.HALT
        
    def update(self):
        self.next_state = self._select_next_state()

        if self.next_state is None:
            self.next_state = 'HALT'
            self.selected_strategy = self._get_new_strategy(self.next_state)

        elif self.next_state != self.current_state:
            self.selected_strategy = self._get_new_strategy(self.next_state)

        self.current_state = self.next_state

        self.ws.play_state.set_strategy(self.selected_strategy)
    
    def str(self):
        pass
    
    def _select_next_state(self):
        referee = self.ws.game_state.game.referee
        next_state = self.current_state
        if self.last_ref_command != referee.command:
            if referee.command == RefereeCommand.HALT:
                self.debug_interface.add_log(1, "Halt robots!")
                next_state = 'HALT'

            elif referee.command == RefereeCommand.STOP or\
                    referee.command == RefereeCommand.GOAL_US or\
                    referee.command == RefereeCommand.GOAL_THEM or\
                    referee.command == RefereeCommand.BALL_PLACEMENT_THEM:
                self.debug_interface.add_log(1, "Game stopped : Robots must keep 50 cm from the ball")
                next_state = 'STOP'

            elif referee.command == RefereeCommand.BALL_PLACEMENT_US:
                self.debug_interface.add_log(1, "Ball placement : we need to place the ball at : " + str(referee.ball_placement_point))
                self.next_state = 'HALT' #TODO send ball new position to strategy...

            elif referee.command == RefereeCommand.FORCE_START:
                self.debug_interface.add_log(1, "Force start : ball is free!")
                next_state = 'FORCE_START'

            elif referee.command == RefereeCommand.NORMAL_START:
                self.debug_interface.add_log(1, "Normal start")
                if self.last_ref_command == RefereeCommand.PREPARE_KICKOFF_US:
                    next_state = 'OFFENSE_KICKOFF'
                elif self.last_ref_command == RefereeCommand.PREPARE_KICKOFF_THEM:
                    next_state = 'DEFENSE_KICKOFF'
                elif self.last_ref_command == RefereeCommand.PREPARE_PENALTY_US:
                    next_state = 'OFFENSE_PENALTY'
                elif self.last_ref_command == RefereeCommand.PREPARE_PENALTY_THEM:
                    next_state = 'DEFENSE_PENALTY'

            elif referee.command == RefereeCommand.TIMEOUT_BLUE or\
                referee.command == RefereeCommand.TIMEOUT_YELLOW:
                self.debug_interface.add_log(1, "Timeout!")
                next_state = 'TIMEOUT'

            elif referee.command == RefereeCommand.PREPARE_KICKOFF_US:
                self.debug_interface.add_log(1, "Prepare kickoff offense!")
                next_state = 'PREPARE_KICKOFF_OFFENSE'

            elif referee.command == RefereeCommand.PREPARE_KICKOFF_THEM:
                self.debug_interface.add_log(1, "Prepare kickoff defense!")
                next_state = 'PREPARE_KICKOFF_DEFENSE'

            elif referee.command == RefereeCommand.PREPARE_PENALTY_US:
                self.debug_interface.add_log(1, "Prepare penalty offense!")
                next_state = 'PREPARE_PENALTY_OFFENSE'

            elif referee.command == RefereeCommand.PREPARE_PENALTY_THEM:
                self.debug_interface.add_log(1, "Prepare penalty defense!")
                next_state = 'PREPARE_PENALTY_DEFENSE'

            else:
                self.debug_interface.add_log(1, "Unknown command... halting all the robots")
                next_state = 'HALT'

        self.last_ref_command = referee.command
        return next_state

    def _get_new_strategy(self, state):
        name = self._get_strategy_name(state)
        return self.ws.play_state.get_new_strategy(name)(self.ws.game_state)

    def _get_strategy_name(self, state):
        # TODO change this
        autonomousStrategies = {
            # Robots must be stopped
            'HALT': 'DoNothing',

            # Robots must stay 50 cm from the ball
            'STOP': 'DoNothing',
            'GOAL_US': 'DoNothing',
            'GOAL_THEM': 'DoNothing',
            'BALL_PLACEMENT_THEM': 'DoNothing',

            # Place the ball to the designated position
            'BALL_PLACEMENT_US': 'DoNothing',

            # The ball is free to take
            'FORCE_START': 'DoNothing',

            'TIMEOUT': 'DoNothing',

            'PREPARE_KICKOFF_OFFENSE': 'DoNothing',
            'PREPARE_KICKOFF_DEFENSE': 'DoNothing',
            'OFFENSE_KICKOFF': 'DoNothing',
            'DEFENSE_KICKOFF': 'DoNothing',

            'PREPARE_PENALTY_OFFENSE': 'DoNothing',
            'PREPARE_PENALTY_DEFENSE': 'DoNothing',
            'OFFENSE_PENALTY': 'DoNothing',
            'DEFENSE_PENALTY': 'DoNothing'
        }
        return autonomousStrategies[state]