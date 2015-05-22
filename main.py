import libtcodpy as libtcod

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50
LIMIT_FPS = 20
playerx = SCREEN_WIDTH / 2
playery = SCREEN_HEIGHT / 2

# Set the font
libtcod.console_set_custom_font('arial10x10.png', libtcod.FONT_TYPE_GREYSCALE |
                                libtcod.FONT_LAYOUT_TCOD)

# Init the screen
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'pyroguecod tutorial',
                          False)

# Set FPS. This does not have an effect for turn-based games
libtcod.sys_set_fps(LIMIT_FPS)


def handle_keys():
    global playerx, playery

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
        playery -= 1
    elif libtcod.console_is_key_pressed(libtcod.KEY_DOWN):
        playery += 1
    elif libtcod.console_is_key_pressed(libtcod.KEY_LEFT):
        playerx -= 1
    elif libtcod.console_is_key_pressed(libtcod.KEY_RIGHT):
        playerx += 1


def main():
    while not libtcod.console_is_window_closed():
        global playerx, playery

        # Set default text color to white
        libtcod.console_set_default_foreground(0, libtcod.white)

        # Place the main player on the screen
        libtcod.console_put_char(0, playerx, playery, '@', libtcod.BKGND_NONE)

        # Update the changes to the screen. Always keep this at the bottom.
        libtcod.console_flush()

        # Clear the trailing character
        libtcod.console_put_char(0, playerx, playery, ' ', libtcod.BKGND_NONE)

        # handle keys and exit the game if needed
        exit = handle_keys()
        if exit:
            break


if __name__ == '__main__':
    main()
