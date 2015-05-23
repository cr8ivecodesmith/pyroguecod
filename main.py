import libtcodpy as libtcod

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50
LIMIT_FPS = 20

# Set the font
libtcod.console_set_custom_font('arial10x10.png', libtcod.FONT_TYPE_GREYSCALE |
                                libtcod.FONT_LAYOUT_TCOD)

# Init the main screen
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'pyroguecod tutorial',
                          False)

# Init an off-screen console to be used as a buffer
con = libtcod.console_new(SCREEN_WIDTH, SCREEN_HEIGHT)

# Set FPS. This does not have an effect for turn-based games
libtcod.sys_set_fps(LIMIT_FPS)


class Object(object):
    """ Generic object class

    Represents the player, monster, an item, the stairs, wall, etc. Its always
    represented by a character on the screen.

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


def handle_keys(player):

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
    if libtcod.console_is_key_pressed(libtcod.KEY_UP):
        player.move(0, -1)
    elif libtcod.console_is_key_pressed(libtcod.KEY_DOWN):
        player.move(0, 1)
    elif libtcod.console_is_key_pressed(libtcod.KEY_LEFT):
        player.move(-1, 0)
    elif libtcod.console_is_key_pressed(libtcod.KEY_RIGHT):
        player.move(1, 0)


def main():
    player = Object(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2, '@', libtcod.white)
    npc = Object(SCREEN_WIDTH / 2 - 5, SCREEN_HEIGHT / 2, '@', libtcod.yellow)
    objects = [npc, player]

    while not libtcod.console_is_window_closed():

        # Set default off-screen text color to white
        libtcod.console_set_default_foreground(con, libtcod.white)

        # Place the game objects on the off-screen
        for obj in objects:
            obj.draw()

        # Blit the contents of the off-screen to the main screen
        libtcod.console_blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)

        # Update the changes to the screen. Always keep this at the bottom.
        libtcod.console_flush()

        # Clear characters on the off-screen
        for obj in objects:
            obj.clear()

        # handle keys and exit the game if needed
        exit = handle_keys(player)
        if exit:
            break


if __name__ == '__main__':
    main()
