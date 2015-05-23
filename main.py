"""
PyRogueCOD - A python roguelike experiment using libtcod.

"""
import pdb
import libtcodpy as libtcod


# Global constants

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

LIMIT_FPS = 20

MAP_WIDTH = 80
MAP_HEIGHT = 45

color_dark_wall = libtcod.Color(0, 0, 100)
color_dark_ground = libtcod.Color(50, 50, 150)


class Tile(object):
    """ A tile on the map and its properties

    """
    def __init__(self, blocked, block_sight=None):
        self.blocked = blocked

        # By default, if a tile is blocked, it also blocks sight.
        self.block_sight = blocked if block_sight is None else block_sight


class Object(object):
    """ Generic object class

    Represents the player, monster, an item, the stairs, wall, etc. Its always
    represented by a character on the screen.

    Requires the ff. variables to be initialized prior to using this class:
    - con: off-screen console

    """

    def __init__(self, x, y, char, color):
        self.x = x
        self.y = y
        self.char = char
        self.color = color

    def move(self, dx, dy):
        """ Move by the given amount.

        """
        self.x += dx
        self.y += dy

    def draw(self):
        """ Set the color then draw the character that represents this object
            at its position.

        """
        libtcod.console_set_default_foreground(con, self.color)
        libtcod.console_put_char(con, self.x, self.y, self.char,
                                 libtcod.BKGND_NONE)

    def clear(self):
        """ Erase the character that represents this object.

        """
        libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)


def handle_keys():
    """ Handle key input from the user.

    Requires the ff. variables to be initialized prior to calling this function:
    - player: Object instance for the main character.

    """

    # Use this to make movement turn-based
    key = libtcod.console_wait_for_keypress(True)

    # Use this instead to make movement real-time
    # key = libtcod.console_check_for_keypress()

    if key.vk == libtcod.KEY_ENTER and key.lalt:
        # Alt+Enter: Toggles fullscreen
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
    elif key.vk == libtcod.KEY_ESCAPE:
        # Exit the game
        return True

    # movement
    if libtcod.console_is_key_pressed(libtcod.KEY_UP) or key.c == ord('k'):
        player.move(0, -1)
    elif libtcod.console_is_key_pressed(libtcod.KEY_DOWN) or key.c == ord('j'):
        player.move(0, 1)
    elif libtcod.console_is_key_pressed(libtcod.KEY_LEFT) or key.c == ord('h'):
        player.move(-1, 0)
    elif libtcod.console_is_key_pressed(libtcod.KEY_RIGHT) or key.c == ord('l'):
        player.move(1, 0)


def make_map():
    """ Generates the map coordinates

    Creates the global var `map`.

    """
    global map

    # Fill map with unblocked tiles
    # Access the map: map[x][y]
    map = [[Tile(False) for y in range(MAP_HEIGHT)]
           for x in range(MAP_WIDTH)]

    # Add some "pillars" on the map.
    map[30][22].blocked = True
    map[30][22].block_sight = True
    map[50][22].blocked = True
    map[50][22].block_sight = True


def render_all():
    """ Draw the game objects and the map.

    Requires the ff. variables to be initialized prior to calling this function:
    - objects: game objects list
    - map: global map coordinates
    - con: off-screen console

    """
    global color_light_wall
    global color_light_ground

    # Go through all the tiles and set their color
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            wall = map[x][y].block_sight
            if wall:
                libtcod.console_set_char_background(con, x, y, color_dark_wall,
                                                    libtcod.BKGND_SET)
            else:
                libtcod.console_set_char_background(con, x, y,
                                                    color_dark_ground,
                                                    libtcod.BKGND_SET)

    # Place the game objects on the off-screen
    for obj in objects:
        obj.draw()

    # Blit the contents of the off-screen to the main screen
    libtcod.console_blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)


if __name__ == '__main__':
    """ Initialization of required variables and game loop.

    """

    # Set the font.
    libtcod.console_set_custom_font('arial10x10.png',
                                    libtcod.FONT_TYPE_GREYSCALE |
                                    libtcod.FONT_LAYOUT_TCOD)

    # Init the main screen.
    libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT,
                              'pyroguecod tutorial', False)

    # Init an off-screen console to be used as a buffer.
    con = libtcod.console_new(SCREEN_WIDTH, SCREEN_HEIGHT)

    # Set FPS. This does not have an effect for turn-based games.
    libtcod.sys_set_fps(LIMIT_FPS)

    # Create the object representing the player.
    player = Object(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2, '@', libtcod.white)

    # Create an NPC
    npc = Object(SCREEN_WIDTH / 2 - 5, SCREEN_HEIGHT / 2, '@', libtcod.yellow)

    # Init list of game objects.
    objects = [npc, player]

    # Generate map coordinates.
    make_map()


    while not libtcod.console_is_window_closed():

        # Render the screen.
        render_all()

        libtcod.console_flush()

        # Clear characters on the off-screen
        for obj in objects:
            obj.clear()

        # handle keys and exit the game if needed
        exit = handle_keys()
        if exit:
            break
