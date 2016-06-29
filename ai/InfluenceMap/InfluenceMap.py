# Under MIT License, see LICENSE.txt

from math import ceil, sqrt
from os import remove
import numpy

from RULEngine.Util.constant import *
from RULEngine.Util.Position import Position


from ai.Algorithm.IntelligentModule import IntelligentModule

__author__ = 'RoboCupULaval'


class InfluenceMap(IntelligentModule):
    """
    Une classe représentant une influence map d'un terrain de robosoccer. C'est une matrice de cellule représentant le
    terrain auquelle on ajoute des points avec des influences qui se propajent sur le reste du terrain.

    La matrice et le code respecte le format suivant:
        - axe X ou axe 0 est l'axe représentant les rangées / l'axe 0 de la matrice /
          la largeur (axe Y) du terrain physique
        - axe Y ou axe 1 est l'axe représentant les colonnes / l'axe 1 de la matrice /
          la longueur (axe X) du terrain physique
        - Le point d'origine (0, 0) se situe au coin supérieur gauche du terrain physique.

    L'algorithm de propagation de l'influence est:
    (force appliqué à la case) = (force du point d'origine de l'influence) * ((facteur de réduction) ** (distance))
    transfomé en int arrondie vers 0.
    """

    def __init__(self, pInfoManager, resolution=100, strengthdecay=0.8, strengthpeak=100, effectradius=8):
        """
        Constructeur de la classe InfluenceMap

        Args:
            pInfoManager:  référence vers l'InfoManager
            resolution:    résolution des cases (défaut = 100)
            strengthdecay: facteur de réduction de l'influence par la distance (défaut = 0.8)
            strengthpeak:  maximum de la force appliquable par un point (est aussi le min) (défaut = 100)
            effectradius:  distance qui borne la propagation de l'influence autour de l'origine (défaut = 40)
        """
        assert (isinstance(resolution, int))
        assert (isinstance(strengthdecay, float))
        assert (0 < strengthdecay < 1)
        assert (isinstance(strengthpeak, int))
        assert (0 < strengthpeak)
        assert (isinstance(effectradius, int))
        assert (0 < effectradius)

        super().__init__(pInfoManager)

# ****************************************************************************************
# ***************** REMOVE! **************************************************************
        # todo see how to better implement a graphic representation!
        # this option is not very useful anymore...
        numpy.set_printoptions(threshold=10000)
        # GOD NO!
        try:
            remove("IMBoard")
            remove("Stencil")
        except OSError:
            print("Nothing to remove!")
# ****************************************************************************************

        # board parameters
        self._resolution = resolution
        self._strengthdecay = strengthdecay
        self._strengthpeak = strengthpeak
        self._effectradius = effectradius
        self._borderstrength = -strengthpeak * 0.03  # TODO change this variable for something not out of thin air!

        # point parameters
        self._ballpositiononboard = ()
        self._friendly_bots_on_board = []
        self._enemy_bots_on_board = []

        number_of_rows_and_columns = self.calculate_rows_and_columns()
        self._numberofrows = number_of_rows_and_columns[0]
        self._numberofcolumns = number_of_rows_and_columns[1]

        self.adjust_effect_radius()

        self._stencil = self.create_stencil_of_point_and_influence()

        self._starterboard = self.create_standard_influence_board()
        self._board = self.create_standard_influence_board()

# **********************************************************************************************************
# ********************************* Getter / Setter ********************************************************
    def get_board(self):
        """
        Returns: self._board, l'array utiliser pour calculer l'influence map.
        """
        return self._board

    def get_starterboard(self):
        """
        Returns: self._starterboard, l'array utiliser pour calculer les bordures, les buts et autres points pré match.
        """
        return self._starterboard

# ****************************************************************************************
# ****************************** Initialization ******************************************
    def calculate_rows_and_columns(self):
        """
        Utilise la resolution pour calculer le nombre de rangée(rows) et de colonne(columns) pour le terrain

        Returns: tuple (int * int), le nombre de rangées et le nombre de colonnes
        """

        numberofrow = (abs(FIELD_Y_BOTTOM) + FIELD_Y_TOP) / self._resolution
        numberofcolumn = (abs(FIELD_X_LEFT) + FIELD_X_RIGHT) / self._resolution

        numberofrow = int(ceil(numberofrow))
        numberofcolumn = int(ceil(numberofcolumn))

        return numberofrow, numberofcolumn

    def create_standard_influence_board(self):
        """
        Crée un objet numpy.ndarray, une liste à 2 dimension de self._numberofrows par self._numberofcolumns d'int16.

        Returns: Un numpy.ndarray d'int16 de self._numberofrows par self._numberofcolumns.
        """
        return numpy.zeros((self._numberofrows, self._numberofcolumns), numpy.int16)

    def adjust_effect_radius(self):
        """
        Permet d'ajuster le rayon d'effet de l'influence (self._effectradius) si celui-ci éxède la propagation normale.

        Si la propagation de l'influence se retrouve à zéro avant d'avoir atteint le rayon d'effet défini à la création
        de la classe, cette méthode l'ajuste pour quelle donne exactement le rayon qui permet d'afficher tous les points
        qui ne donnent pas zéro.
        """
        distance_from_center = 0
        starting_point = self._strengthpeak
        while starting_point >= 1:
            distance_from_center += 1
            decay = int((self._strengthpeak * (self._strengthdecay ** distance_from_center)))
            starting_point = decay
        # TODO check this
        """
        if (self._effectradius * 2) > self._numberofrows:
            self._effectradius = self._numberofrows / 2 - 1
        """
        if self._effectradius > distance_from_center:
            self._effectradius = distance_from_center

    def initialize_borders(self):
        """
        Ajoute des bordures au starterboard et au board.
        """
        temp_array = self.create_standard_influence_board()
        self._put_and_propagate_borders(temp_array)
        numpy.add(temp_array, self._starterboard, out=self._starterboard)
        numpy.add(temp_array, self._board, out=self._board)

    def _put_and_propagate_borders(self, board_to_apply):
        """
        Mets des bordures sur un array numpy.ndarray vierge.

        Args:
            board_to_apply: Un numpy.ndarray un array vierge pour y ajouter des bordures.
        """
        board_to_apply[0] = self._borderstrength
        board_to_apply[:, 0] = self._borderstrength

        # keep the effectradius low while making the border speed up greatly the initialization, also you don't need
        # so much border
        # TODO see if this variable is okay, maybe change the way it is determined
        border_variance = 2
        temporary_effectradius = int(ceil(ROBOT_RADIUS / self._resolution)) + border_variance
        # TODO make this faster? use the stencil function or make it in cython?

        # TODO make sure this does what you think it does.
        # Top border
        for border in range(0, self._numberofcolumns):
            # only for the rows affected by the change.
            for x in range(0, temporary_effectradius):

                if border - temporary_effectradius - 1 < 0:
                    columnmin = 0
                else:
                    columnmin = border - temporary_effectradius - 1

                if border + temporary_effectradius + 1 > self._numberofcolumns:
                    columnmax = self._numberofcolumns
                else:
                    columnmax = border + temporary_effectradius + 1
                # for every columns affected
                for y in range(columnmin, columnmax):
                    if ((x - 0) ** 2 + (y - border) ** 2) <= temporary_effectradius ** 2:
                        decay = int((self._borderstrength * (self._strengthdecay **
                                                             self.distance(0, border, x, y))))
                        board_to_apply[x, y] += decay

        # left border
        for border in range(0, self._numberofrows):

            for y in range(0, temporary_effectradius):

                if border - temporary_effectradius - 1 < 0:
                    rowmin = 0
                else:
                    rowmin = border - temporary_effectradius - 1

                if border + temporary_effectradius + 1 > self._numberofrows:
                    rowmax = self._numberofrows
                else:
                    rowmax = border + temporary_effectradius + 1

                for x in range(rowmin, rowmax):
                    if ((x - border) ** 2 + (y - 0) ** 2) <= temporary_effectradius ** 2:
                        decay = int((self._borderstrength * (self._strengthdecay **
                                                             self.distance(border, 0, x, y))))
                        board_to_apply[x, y] += decay

        # Prend l'image créer et la flip l-r et u-d puis additionne
        # todo simplify
        temp_inverse_board = numpy.copy(board_to_apply)
        temp_inverse_board = temp_inverse_board[:, ::-1]
        temp_inverse_board = temp_inverse_board[::-1, ...]
        board_to_apply += temp_inverse_board

    def initialize_goals(self):
        """
        Mets des buts sur le starterboard et le board
        """
        # todo fetch which side we are on.
        temp_array = self.create_standard_influence_board()
        v_h_goal_offset = (self._calculate_goal_vertical_offset(), self._calculate_goal_horizontal_offset())
        self._put_goals_and_propagate(v_h_goal_offset, temp_array)
        numpy.add(temp_array, self._starterboard, out=self._starterboard)
        numpy.add(temp_array, self._board, out=self._board)

    def _calculate_goal_vertical_offset(self):
        """
        Calcule la dimension vertical du but p/r à la résolution.
        Returns: int la valeur verticale du but ajusté à la résolution
        """
        return int(ceil(FIELD_GOAL_Y_TOP / self._resolution))

    def _calculate_goal_horizontal_offset(self):
        """
        Calcule la dimension horizontale du but p/r à la résolution.
        Returns: int la valeur horizontale du but ajusté à la résolution
        """
        return int(ceil(FIELD_GOAL_SEGMENT / self._resolution))

    def _put_goals_and_propagate(self, v_h_offset, board_to_apply):
        """
        Mets des buts sur un numpy.ndarray vierge.

        Args:
            v_h_offset: tuple la dimension verticale et horizontale des buts.
        """
        # TODO take into account what team you are ie: orientation and strength adjustment
        # TODO remove that next if?
        if self._numberofrows % 2 == 0:
            for x in range(int(self._numberofrows / 2 - v_h_offset[0]),
                           int(self._numberofrows / 2 + v_h_offset[0]) + 1):
                self.add_point_and_propagate_stencil(x, 0, board_to_apply)

        numpy.add((numpy.negative(board_to_apply[:, ::-1])), board_to_apply, out=board_to_apply)
        numpy.savetxt("Debug", board_to_apply, fmt='%5i')

    def create_stencil_of_point_and_influence(self):
        """
        Crée une image d'un point de valeur maximale pour pouvoir ajouter des points sans recalculer chaque case. Store
        le stencil résultant dans la variable de classe self._stencil
        """
        # todo cyton maybe?
        stencil = numpy.zeros((self._effectradius * 2 + 1, self._effectradius * 2 + 1), numpy.int16)
        center = (self._effectradius, self._effectradius)
        it = numpy.nditer(stencil, flags=['multi_index'], op_flags=['writeonly'])
        while not it.finished:
            if ((it.multi_index[0] - center[0]) ** 2 + (it.multi_index[1] - center[1]) ** 2) <= self._effectradius ** 2:

                decay = int((self._strengthpeak * (self._strengthdecay **
                                                   self.distance(it.multi_index[0], it.multi_index[1], center[0],
                                                                 center[1]))))
                stencil[it.multi_index[0], it.multi_index[1]] += decay
            it.iternext()

        return stencil

# ******************************************************************************************
# **********************Adding points and influences methods *******************************

    def get_fitted_stencil(self, row, column, inverse=False):
        """
        Ajuste le stencil de la classe (self._stencil) pour pouvoir l'utiliser dans le board.

        Ajuste la valeur des cases en fonction de la valeur de force voulue, (max et min seulement).
        Coupe le stencil et/ou ajoute des rangées et colonnes pour ajusté le stencil au format du board.

        Args:
            row: int la rangée du point d'origine de la force
            column: int La colonne du point d'origine de la force
            inverse: bool True prend le max de force, False prende le min de force

        Returns: numpy.ndarray de format du board avec le point proprement placé.

        """
        assert isinstance(row, int)
        assert (0 <= row < self._numberofrows)
        assert isinstance(column, int)
        assert (0 <= column < self._numberofcolumns)
        assert isinstance(inverse, bool)

        temp_stencil = numpy.copy(self._stencil)
        v_borders_left, v_borders_right, h_borders_top, h_borders_bot = False, False, False, False

        if inverse:
            temp_stencil = numpy.negative(temp_stencil)

        # emmagasine le nombre de rangée coupé et sert seulement si le point chevauche les deux bordures.
        both_borders_adjustment = 0

        if self._effectradius - row >= 0:
            temp_stencil = temp_stencil[(self._effectradius - row):, ...]
            h_borders_top = True
            both_borders_adjustment = self._effectradius - row

        if self._effectradius + row >= self._numberofrows:
            if both_borders_adjustment or self._effectradius - row == 0:
                temp_stencil = temp_stencil[0:(self._effectradius + (self._numberofrows -
                                            row) - both_borders_adjustment), ...]
                h_borders_bot = True
            else:
                temp_stencil = temp_stencil[0:(self._effectradius + (self._numberofrows -
                                            row) + 1), ...]
                h_borders_bot = True

        if self._effectradius - column >= 0:
            temp_stencil = temp_stencil[..., (self._effectradius - column):]
            v_borders_left = True

        if self._effectradius + column >= self._numberofcolumns:
            temp_stencil = temp_stencil[..., 0:(self._effectradius + (self._numberofcolumns - column))]
            v_borders_right = True

        if h_borders_top and h_borders_bot:
            pass
        elif h_borders_top:
            h_bot_stack = numpy.zeros((self._numberofrows - (self._effectradius + row + 1), temp_stencil.shape[1]),
                                      numpy.int16)
            temp_stencil = numpy.concatenate((temp_stencil, h_bot_stack), axis=0)
        elif h_borders_bot:
            h_top_stack = numpy.zeros((self._numberofrows - ((self._numberofrows - row) +
                                       self._effectradius) - 1, temp_stencil.shape[1]), numpy.int16)
            temp_stencil = numpy.concatenate((h_top_stack, temp_stencil), axis=0)
        else:
            h_bot_stack = numpy.zeros((self._numberofrows - (self._effectradius + row + 1), temp_stencil.shape[1]),
                                      numpy.int16)
            h_top_stack = numpy.zeros((row - self._effectradius, temp_stencil.shape[1]), numpy.int16)
            temp_stencil = numpy.concatenate((temp_stencil, h_bot_stack), axis=0)
            temp_stencil = numpy.concatenate((h_top_stack, temp_stencil), axis=0)

        if v_borders_left and v_borders_right:
            pass
        elif v_borders_left:
            v_right_stack = numpy.zeros((temp_stencil.shape[0],
                                         self._numberofcolumns - (self._effectradius + column + 1)), numpy.int16)
            temp_stencil = numpy.concatenate((temp_stencil, v_right_stack), axis=1)
        elif v_borders_right:

            v_left_stack = numpy.zeros((temp_stencil.shape[0], self._numberofcolumns -
                                        ((self._numberofcolumns - column) + self._effectradius)), numpy.int16)
            temp_stencil = numpy.concatenate((v_left_stack, temp_stencil), axis=1)
        else:
            v_right_stack = numpy.zeros((temp_stencil.shape[0],
                                         self._numberofcolumns - (self._effectradius + column + 1)), numpy.int16)
            v_left_stack = numpy.zeros((temp_stencil.shape[0], column - self._effectradius), numpy.int16)
            temp_stencil = numpy.concatenate((temp_stencil, v_right_stack), axis=1)
            temp_stencil = numpy.concatenate((v_left_stack, temp_stencil), axis=1)

        return temp_stencil

    def add_point_and_propagate_influence(self, row, column, board_to_apply, strength=0):
        """
        Pose un point et propage son influence sur l'array donné.

        Cette méthode sert seulement au cas ou le point n'a pas une force égale à +- le maximum de
        force(self._strengthpeak)

        Args:
            row: int la rangée du point d'origine de la force
            column: int La colonne du point d'origine de la force
            board_to_apply: numpy.ndarray l'array auqelle on applique le point doit avoir le format du board
            strength: int la force du point à appliquer
        """
        assert (isinstance(row, int))
        assert (isinstance(column, int))
        assert (0 <= row < self._numberofrows)
        assert (0 <= column < self._numberofcolumns)
        assert (isinstance(board_to_apply, numpy.ndarray))
        assert (board_to_apply.shape[0] == self._numberofrows)
        assert (board_to_apply.shape[1] == self._numberofcolumns)
        assert (isinstance(strength, int))
        assert (-self._strengthpeak <= strength <= self._strengthpeak)

        # todo check the following if statements please
        if row - self._effectradius < 0:
            rowmin = 0
        else:
            rowmin = row - self._effectradius

        if row + self._effectradius > self._numberofrows - 1:
            rowmax = self._numberofrows - 1
        else:
            rowmax = row + self._effectradius

        if column - self._effectradius - 1 < 1:
            columnmin = 1
        else:
            columnmin = column - self._effectradius - 1

        if column + self._effectradius + 1 > self._numberofcolumns:
            columnmax = self._numberofcolumns
        else:
            columnmax = column + self._effectradius + 1

        it = numpy.nditer(board_to_apply[rowmin:(rowmax+1), columnmin:(columnmax+1)], flags=['multi_index'],
                          op_flags=['readwrite'])

        while not it.finished:
            if ((it.multi_index[0] - (row - rowmin)) ** 2 + (it.multi_index[1] - (column - columnmin)) ** 2) <= \
                            self._effectradius ** 2:
                it[0] += int((strength * (self._strengthdecay ** self.distance(it.multi_index[0], it.multi_index[1],
                                                                               (row - rowmin), (column - columnmin)))))
            it.iternext()

    def add_point_and_propagate_stencil(self, row, column, board_to_apply, inverse=False):
        """
        Pose un point et propage son influence sur l'array donné.

        Utilise un stencil.

        Args:
            row: int la rangée du point d'origine de la force
            column: int La colonne du point d'origine de la force
            board_to_apply: numpy.ndarray l'array auqelle on applique le point doit avoir le format du board
            inverse: bool True prend le max de force, False prende le min de force
        """
        assert (isinstance(row, int))
        assert (isinstance(column, int))
        assert (isinstance(inverse, bool))
        assert (0 <= row < self._numberofrows)
        assert (0 <= column < self._numberofcolumns)
        assert (isinstance(board_to_apply, numpy.ndarray))
        assert (board_to_apply.shape[0] == self._numberofrows)
        assert (board_to_apply.shape[1] == self._numberofcolumns)

        stencil = self.get_fitted_stencil(row, column, inverse=inverse)
        numpy.add(board_to_apply, stencil, out=board_to_apply)

    def add_square_and_propagate(self, top, bottom, left, right, strength):
        """
        Met un carré de point dans l'array donné.

        Args:
            top: int rangée supérieure du carré
            bottom: int rangée inférieure du carré
            left: int colonne gauche du carré
            right: int colonne droite du carré
            strength: int la force du point à appliquer doit être égale à +- la force maximale(self._strength)
        """
        assert (isinstance(top, int))
        assert (isinstance(bottom, int))
        assert (isinstance(left, int))
        assert (isinstance(right, int))
        assert (0 <= top < self._numberofrows)
        assert (0 <= bottom < self._numberofrows)
        assert (0 <= left < self._numberofcolumns)
        assert (0 <= right < self._numberofcolumns)
        assert (top <= bottom)
        assert (left <= right)
        assert (isinstance(strength, int))
        assert (-self._strengthpeak == strength or self._strengthpeak == strength)

        inverse = False
        if strength == - self._strengthpeak:
            inverse = True

        for x in range(top, bottom):
            for y in range(left, right):
                self.add_point_and_propagate_stencil(x, y, self._board, inverse=inverse)

# ********************************************************************************************************
# **************************************** Generic point finding *****************************************

    def find_closest_point_of_strength_around(self, row, column, strengthrequired, over=True):
        """
        Ne pas utiliser, sert de placement pour replacer plus tard.
        """
        assert (isinstance(row, int))
        assert (isinstance(column, int))
        assert (isinstance(strengthrequired, int))
        assert (0 <= row <= self._numberofrows)
        assert (0 <= column <= self._numberofcolumns)
        assert (-(self._strengthpeak ** 2) <= strengthrequired <= self._strengthpeak ** 2)

        result = []
        counter = 1
        rtop = False
        rbottom = False
        cleft = False
        cright = False
        rowinsidesquare = [row]
        columninsidesquare = [column]

        while not result:

            for x in range(row - counter, row + counter + 1):

                if rtop and rbottom and cleft and cright:
                    result.append(0)
                    break

                if x < 1:
                    rtop = True
                    continue

                if x > self._numberofrows - 1:
                    rbottom = True
                    break

                for y in range(column - counter, column + counter + 1):

                    if y < 1:
                        cleft = True
                        continue

                    if y > self._numberofcolumns - 1:
                        cright = True
                        break

                    if x in rowinsidesquare and y in columninsidesquare:
                        continue

                    if over:
                        if self._board[x, y] >= strengthrequired:
                            result.append((x, y))
                    else:
                        if self._board[x, y] <= strengthrequired:
                            result.append((x, y))

            counter += 1
            rowinsidesquare = range(row - counter + 1, row + counter)
            columninsidesquare = range(column - counter + 1, column + counter)

        if not result[0]:
            result.clear()

        return result

    def find_points_over_strength_square(self, top_row, bot_row, left_column, right_column, strength):

        ind_x, ind_y = numpy.where(self._board[top_row:bot_row, left_column:right_column] >= strength)
        ind_x = ind_x.tolist()
        ind_x = [x+top_row for x in ind_x]
        ind_y = ind_y.tolist()
        ind_y = [x+left_column for x in ind_y]
        indices = zip(ind_x, ind_y)
        return list(indices)

    def find_points_under_strength_square(self, top_row, bot_row, left_column, right_column, strength):

        ind_x, ind_y = numpy.where(self._board[top_row:bot_row, left_column:right_column] <= strength)
        ind_x = ind_x.tolist()
        ind_x = [x+top_row for x in ind_x]
        ind_y = ind_y.tolist()
        ind_y = [x+left_column for x in ind_y]
        indices = zip(ind_x, ind_y)
        return list(indices)

    def find_max_value_in_board(self):
        uniques = numpy.unique(self._board)
        max_in_board = uniques[-1]
        x, y = numpy.where(self._board >= max_in_board)
        x = x.tolist()
        y = y.tolist()
        indices = zip(x, y)
        return max_in_board, indices

    def find_min_value_in_board(self):
        uniques = numpy.unique(self._board)
        min_in_board = uniques[0]
        x, y = numpy.where(self._board <= min_in_board)
        x = x.tolist()
        y = y.tolist()
        indices = zip(x, y)
        return min_in_board, indices

# **********************************************************************************************************
# ************************************ Player representation methods****************************************

    def update_friend_position(self):
        self._friendly_bots_on_board.clear()
        for i in range(self.state.get_count_player):
            friend_position = self.state.get_player_position(i)
            friend_position = self.transform_field_to_board_position(friend_position)
            self._friendly_bots_on_board.append(friend_position)
            self.add_point_and_propagate_stencil(friend_position[0], friend_position[1], self._board, inverse=False)


# **********************************************************************************************************
# ************************************ Foes representation methods *****************************************
    # TODO ask about implementation of foes in infomanager

    def update_foes_position(self):
        pass

# **********************************************************************************************************
# ************************************ Ball representation methods *****************************************

    def update_ball_position(self):
        self._ballpositiononboard = self.transform_field_to_board_position(self.state.get_ball_position())

    def set_ball_position(self, row, column):
        self._ballpositiononboard = (row, column)

    def get_ball_influence(self):
        return self._board[self._ballpositiononboard[0], self._ballpositiononboard[1]]

# **********************************************************************************************************
# ********************************************* misc methods ***********************************************

    def clear_point_on_board(self):
        # todo add a point checking maybe?
        self._board = numpy.copy(self._starterboard)
        self._friendly_bots_on_board.clear()

    def update(self):
        self.clear_point_on_board()
        self.get_list_of_interresting_position()
        self.get_points_from_list_on_board()

    def get_list_of_interresting_position(self):
        pass

    def get_points_from_list_on_board(self):
        # todo change this to better reflect reality
        for x in self._friendly_bots_on_board:
            self.add_point_and_propagate_stencil(x[0], x[1][0], x[1][0])

    def export_board(self):
        return self._board.tolist()

    def transform_field_to_board_position(self, position):
        # TODO see if that holds up
        assert (isinstance(position, Position))
        assert (position.x <= FIELD_X_RIGHT + 100)
        assert (position.x >= FIELD_X_LEFT - 100)
        assert (position.y <= FIELD_Y_TOP + 100)
        assert (position.y >= FIELD_Y_BOTTOM - 100)

        xpos = position.x + ((abs(FIELD_X_LEFT) + FIELD_X_RIGHT) / 2)
        ypos = position.y + ((abs(FIELD_Y_BOTTOM) + FIELD_Y_TOP) / 2)

        xpos = int(round(xpos / self._resolution, 0))
        ypos = int(round(ypos / self._resolution, 0))

        return xpos, ypos

    def transform_board_to_field_position(self, row, column):
        # TODO see if that holds up
        assert (isinstance(row, int))
        assert (isinstance(column, int))
        assert (0 <= row <= self._numberofrows - 2)
        assert (0 <= column <= self._numberofcolumns - 2)

        if row >= self._numberofrows / 2:
            xpos = FIELD_X_LEFT + (column * self._resolution - int(self._resolution / 2))
        else:
            xpos = FIELD_X_LEFT + (column * self._resolution + int(self._resolution / 2))

        if column >= self._numberofcolumns / 2:
            ypos = FIELD_Y_TOP - (row * self._resolution - int(self._resolution / 2))
        else:
            ypos = FIELD_Y_TOP - (row * self._resolution + int(self._resolution / 2))

        tempposition = Position(xpos, ypos)
        return tempposition

    def print_board_to_file(self):
        """
        Create a file in the same running directory with a representation of the current board.
        """

        numpy.savetxt("IMBoard", self._board, fmt='%5i')
        # todo remove this line while not in debug mode
        print(self._numberofrows, "  ", self._numberofcolumns, "  - friendlies =  ", self._friendly_bots_on_board)
        print(self._starterboard.shape[0], " x ", self._starterboard.shape[1], "  erad: ", self._effectradius)

    def str(self):
        # todo comment and make sure this is right!
        return str("Influence Map - ", str(self._numberofrows), " x ", str(self._numberofcolumns))

    def distance(self, x1, y1, x2, y2):
        """
        Retourne la distance entre deux points x et y.

        Args:
            x1: int
            y1: int
            x2: int
            y2: int

        Returns: La distance entre les deux points, aucun type défini.

        """
        # TODO possibly move this function somewhere else
        assert (isinstance(x1, int))
        assert (isinstance(x2, int))
        assert (isinstance(y1, int))
        assert (isinstance(y2, int))
        return sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
