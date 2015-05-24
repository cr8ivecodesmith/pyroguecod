"""
PyRogueCOD - A python roguelike experiment using libtcod.

"""
from __future__ import print_function

import math
import textwrap
import shelve

import libtcodpy as libtcod


# Global constants
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

LIMIT_FPS = 20

MAP_WIDTH = 80
MAP_HEIGHT = 43
LEVEL_SCREEN_WIDTH = 40
CHARACTER_SCREEN_WIDTH = 30

ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30
MAX_ROOM_MONSTERS = 3
MAX_ROOM_ITEMS = 2

FOV_ALGO = 4  # Default FOV algorithm
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT

MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1

LEVEL_UP_BASE = 200
LEVEL_UP_FACTOR = 150

INVENTORY_WIDTH = 50
HEAL_AMOUNT = 4
LIGHTNING_DAMAGE = 20
LIGHTNING_RANGE = 5
CONFUSE_NUM_TURNS = 10
CONFUSE_RANGE = 10
FIREBALL_RADIUS = 3
FIREBALL_DAMAGE = 12

color_dark_wall = libtcod.Color(0, 0, 100)
color_light_wall = libtcod.Color(130, 110, 50)
color_dark_ground = libtcod.Color(50, 50, 150)
color_light_ground = libtcod.Color(200, 180, 50)


class Tile(object):
    """ A tile on the map and its properties

    """
    def __init__(self, blocked, block_sight=None):
        self.explored = False
        self.blocked = blocked

        # By default, if a tile is blocked, it also blocks sight.
        self.block_sight = blocked if block_sight is None else block_sight


class Object(object):
    """ Generic object class

    Represents the player, monster, an item, the stairs, wall, etc. Its always
    represented by a character on the screen.

    """
    def __init__(self, x, y, char, name, color, blocks=False,
                 always_visible=False, fighter=None, ai=None, item=None):
        self.name = name
        self.blocks = blocks
        self.x = x
        self.y = y
        self.char = char
        self.color = color
        self.always_visible = always_visible

        self.fighter = fighter
        if self.fighter:
            # Let the fighter component know its owner.
            self.fighter.owner = self

        self.ai = ai
        if self.ai:
            # Let the ai component know its owner.
            self.ai.owner = self

        self.item = item
        if self.item:
            self.item.owner = self

    def move(self, dx, dy):
        """ Move by the given amount.

        """
        if not is_blocked(self.x + dx, self.y + dy):
            self.x += dx
            self.y += dy

    def move_towards(self, target_x, target_y):
        """ Basic path-finding functionality.

        Get a vector from the object to the target, then normalize so it has
        the same direction but has a length of exactly 1 tile. Then we round it
        so the resulting vector is an integer and not a fraction (dx and dy can
        only take values that is -1, 1, or 0). Finally, the object moves by
        this amount.

        """
        # vector and distance from this object to its target
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx**2 + dy**2)

        # normalize it to lenght 1 (preserving direction), then round it and
        # convert to int so the movement is restricted to the map grid.
        dx = int(round(dx / distance))
        dy = int(round(dy / distance))
        self.move(dx, dy)

    def distance_to(self, other):
        """ Return the distance to another object.

        """
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx**2 + dy**2)

    def distance(self, x, y):
        """ Return distance to a given coordinate

        """
        dx = x - self.x
        dy = y - self.y
        return math.sqrt(dx**2 + dy**2)

    def send_to_back(self):
        """ Have this object drawn first.

        """
        global objects
        objects.remove(self)
        objects.insert(0, self)

    def draw(self):
        """ Set the color then draw the character that represents this object
            at its position only when its within the FOV.

        """
        global con, map

        if ((in_fov(self.x, self.y)) or (self.always_visible and
                                         map[self.x][self.y].explored)):
            libtcod.console_set_default_foreground(con, self.color)
            libtcod.console_put_char(con, self.x, self.y, self.char,
                                     libtcod.BKGND_NONE)

    def clear(self):
        """ Erase the character that represents this object.

        """
        global con

        libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)


class Fighter(object):
    """ Combat-type Object component.

    """
    owner = None

    def __init__(self, hp, defense, power, xp, death_function=None):
        self.max_hp = hp
        self.hp = hp
        self.defense = defense
        self.power = power
        self.xp = xp
        self.death_function = death_function

    def take_damage(self, damage):
        global player

        if damage > 0:
            self.hp -= damage

        # Call the Object's death function if there's one upon death.
        if self.hp <= 0:
            function = self.death_function
            if function:
                function(self.owner)
                if self.owner != player:
                    player.fighter.xp += self.xp

    def attack(self, target):
        # A simple damage formula.
        damage = self.power - target.fighter.defense

        if damage:
            msg = '{} attacks {} for {} hit points.'.format(
                  self.owner.name.capitalize(), target.name, damage)
            message(msg)
            target.fighter.take_damage(damage)
        else:
            msg = '{} attacks {} but it has not effect!'.format(
                  self.owner.name.capitalize(), target.name)
            message(msg)

    def heal(self, amount):
        heal_value = self.hp + amount
        if heal_value >= self.max_hp:
            self.hp = self.max_hp
        else:
            self.hp += amount


class BasicMonster(object):
    """ AI Object component for basic monsters

    """
    owner = None

    def take_turn(self):
        global player

        monster = self.owner
        if in_fov(monster.x, monster.y):
            # move towards the player
            if monster.distance_to(player) >= 2:
                monster.move_towards(player.x, player.y)
            elif player.fighter.hp > 0:
                monster.fighter.attack(player)


class ConfusedMonster(object):
    """ AI Object component for confused monsters

    Reverts back to the original AI after a while.

    """
    owner = None

    def __init__(self, old_ai, num_turns=CONFUSE_NUM_TURNS):
        self.old_ai = old_ai
        self.num_turns = num_turns

    def take_turn(self):
        global player

        if self.num_turns > 0:
            self.owner.move(libtcod.random_int_choice(0, -1, 1),
                            libtcod.random_int_choice(0, -1, 1))
            self.num_turns -= 1
        else:
            self.owner.ai = self.old_ai
            message('The {} is no longer confused!'.format(self.owner.name),
                    libtcod.red)


class Item(object):
    """ Item Object component.

    Objects that can be picked up and used.

    """
    owner = None

    def __init__(self, use_function=None):
        self.use_function = use_function

    def pick_up(self):
        global inventory
        global objects

        if len(inventory) >= 26:
            message('Your inventory is full, cannot pick up {}.'.format(
                    self.owner.name), libtcod.red)
        else:
            inventory.append(self.owner)
            objects.remove(self.owner)
            message('You picked up the {}!'.format(self.owner.name),
                    libtcod.green)

    def use(self):
        global inventory

        if not self.use_function:
            message('The {} cannot be used.'.format(self.owner.name))
        else:
            if self.use_function() != 'cancelled':
                # destroy after use unless it was cancelled.
                inventory.remove(self.owner)
            else:
                message('Cancelled.', libtcod.red)

    def drop(self):
        global player, objects, inventory

        objects.append(self.owner)
        inventory.remove(self.owner)
        self.owner.x = player.x
        self.owner.y = player.y
        message('You dropped the {}.'.format(self.owner.name), libtcod.yellow)


class Rect(object):
    """ A rectangle on the map used to characterize a room.

    """
    def __init__(self, x, y, w, h):
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h

    def center(self):
        """ All rooms will be connected via their center coordinates.

        """
        center_x = (self.x1 + self.x2) / 2
        center_y = (self.y1 + self.y2) / 2
        return (center_x, center_y)

    def intersect(self, other):
        """ Return True if this object intersects with the `other` room.

        """
        return (self.x1 <= other.x2 and self.x2 >= other.x1 and
                self.y1 <= other.y2 and self.y2 >= other.y1)


def create_room(room):
    """ Go through the tiles in the rectangle and make them passable.

    """
    global map

    for x in range(room.x1 + 1, room.x2):
        for y in range(room.y1 + 1, room.y2):
            map[x][y].blocked = False
            map[x][y].block_sight = False


def create_h_tunnel(x1, x2, y):
    """ Carve a horizontal tunnel.

    """
    global map

    # Using the min and max creatively here, otherwise we'll have to determine
    # which one is larger or smaller to place on the appropriate range args.
    for x in range(min(x1, x2), max(x1, x2) + 1):
        map[x][y].blocked = False
        map[x][y].block_sight = False


def create_v_tunnel(y1, y2, x):
    """ Carve a vertical tunnel.

    """
    global map

    # Using the min and max creatively here, otherwise we'll have to determine
    # which one is larger or smaller to place on the appropriate range args.
    for y in range(min(y1, y2), max(y1, y2) + 1):
        map[x][y].blocked = False
        map[x][y].block_sight = False


def random_choice_index(chances):
    """ Determine where in the list the random choice lands and return the
        corresponding index.

    """
    dice = libtcod.random_get_int(0, 1, sum(chances))

    running_sum = 0
    choice = 0
    for idx, value in enumerate(chances):
        running_sum += value
        if dice <= running_sum:
            return idx


def random_choice(chances_dict):
    """ Pick a random item in the dictionary and return the key.

    """
    chances = chances_dict.values()
    keys = chances_dict.keys()
    return keys[random_choice_index(chances)]


def place_objects(room):
    """ Place objects in a room.

    """
    global objects

    monster_chances = {
        'orc': 80,
        'goblin': 20,
    }
    item_chances = {
        'healing': 70,
        'lightning': 10,
        'fireball': 10,
        'confuse': 10,
    }

    num_monsters = libtcod.random_get_int(0, 0, MAX_ROOM_MONSTERS)
    num_items = libtcod.random_get_int(0, 0, MAX_ROOM_ITEMS)

    # Place the monsters.
    for i in range(num_monsters):
        # NOTE: We can play around this some more to place different kinds of
        # monsters or groups of monsters. We'll settle with this for now.

        # Choose a random a place for this monster in the room.
        x = libtcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
        y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)

        if not is_blocked(x, y):
            monster = None
            choice = random_choice(monster_chances)
            if choice == 'orc':
                fighter_component = Fighter(hp=10, defense=0, power=3, xp=35,
                                            death_function=monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 'o', 'orc', libtcod.desaturated_green,
                                 blocks=True, fighter=fighter_component,
                                 ai=ai_component)
            elif choice == 'troll':
                fighter_component = Fighter(hp=16, defense=1, power=4, xp=100,
                                            death_function=monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 'T', 'troll', libtcod.darker_green,
                                 blocks=True, fighter=fighter_component,
                                 ai=ai_component)

            if monster:
                objects.append(monster)

    # Place the items
    for i in range(num_items):
        # Choose a random a place for this item in the room.
        x = libtcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
        y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)

        if not is_blocked(x, y):
            item = None
            choice = random_choice(item_chances)
            if choice == 'healing':
                name = 'healing potion'
                item_component = Item(use_function=cast_heal)
                item = Object(x, y, '!', name, libtcod.violet,
                              always_visible=True, item=item_component)
            elif choice == 'lightning':
                name = 'scroll of lightning bolt'
                item_component = Item(use_function=cast_lightning)
                item = Object(x, y, '#', name, libtcod.light_yellow,
                              always_visible=True, item=item_component)
            elif choice == 'fireball':
                name = 'scroll of fireball'
                item_component = Item(use_function=cast_fireball)
                item = Object(x, y, '#', name, libtcod.light_yellow,
                              always_visible=True, item=item_component)
            elif choice == 'confusion':
                name = 'scroll of confusion'
                item_component = Item(use_function=cast_confuse)
                item = Object(x, y, '#', name, libtcod.light_yellow,
                              always_visible=True, item=item_component)

            if item:
                objects.append(item)
                item.send_to_back()


def is_blocked(x, y):
    """ Check whether a location on the map has a tile or a blocking object.

    """
    global map

    if map[x][y].blocked:
        return True

    for obj in objects:
        if obj.blocks and obj.x == x and obj.y == y:
            return True

    return False


def in_fov(x, y):
    """ Check if given coordinates is within the fov.

    """
    global player
    global fov_map
    return True if libtcod.map_is_in_fov(fov_map, x, y) else False


def check_level_up():
    """ See if the player's experience is enough to level up.

    """
    global player

    level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR

    if player.fighter.xp >= level_up_xp:
        player.level += 1
        player.fighter.xp -= level_up_xp
        message('Your battle skills grow stronger! You reached level '
                '{}!'.format(player.level), libtcod.yellow)

        choice = None
        choices = [
            'Constitution (+20 HP, from {})'.format(player.fighter.max_hp),
            'Strength (+1 attack, from {})'.format(player.fighter.power),
            'Agility (+1 defense, from {})'.format(player.fighter.defense)
        ]

        while choice == None:
            choice = menu('Level up! Choose a stat to raise:\n', choices,
                          LEVEL_SCREEN_WIDTH)

        if choice == 0:
            player.fighter.max_hp += 20
            player.fighter.hp += 20
        elif choice == 1:
            player.fighter.power += 1
        elif choice == 2:
            player.fighter.defense += 1


def closest_monster(max_range):
    """ Find the closest monster within the given range and FOV

    """
    global objects
    global player

    closest_enemy = None
    closest_dist = max_range + 1  # start with (slightly more) max range.

    for obj in objects:
        if obj.fighter and obj != player and in_fov(obj.x, obj.y):
            dist = player.distance_to(obj)
            if dist < closest_dist:
                closest_enemy = obj
                closest_dist = dist
    return closest_enemy


def target_tile(max_range=None):
    """ Return the coordinates of the tile clicked by the player

    Returns (None, None) if right-click is used instead.

    NOTE: Challenge yourself by creating a keyboard targeting interface.

    """
    global key, mouse, player
    while True:
        # Render the screen, erase the inventory, show object names under the
        # mouse.
        libtcod.console_flush()
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS |
                                    libtcod.EVENT_MOUSE, key, mouse)
        render_all()

        x, y = (mouse.cx, mouse.cy)

        if (
            mouse.lbutton_pressed and in_fov(x, y) and max_range is None or
            player.distance(x, y) <= max_range
        ):
            return (x, y)
        if mouse.rbutton_pressed or key.vk == libtcod.KEY_ESCAPE:
            return (None, None)


def target_monster(max_range=None):
    """ Return the monster clicked within FOV or None if cancelled.

    """
    global objects, player

    while True:
        x, y = target_tile(max_range)
        if x is None:
            return None

        for obj in objects:
            if obj.x == x and obj.y == y and obj.fighter and obj != player:
                return obj


def player_move_or_attack(dx, dy):
    """ Handle player action to either move or attack

    """
    global fov_recompute
    global objects
    global player

    # The coordinates where the player is moving/attacking.
    x = player.x + dx
    y = player.y + dy

    # Try to find an attackable object there.
    target = None
    for obj in objects:
        if obj.fighter and obj.x == x and obj.y == y:
            target = obj
            break

    # Attack if a target was found, move otherwise.
    if target:
        player.fighter.attack(target)
    else:
        player.move(dx, dy)
        fov_recompute = True


def cast_heal():
    """ Heal the player

    """
    global player

    if player.fighter.hp == player.fighter.max_hp:
        message('You are already at full health.', libtcod.red)
        return 'cancelled'
    message('Your wounds start to feel better!', libtcod.light_violet)
    player.fighter.heal(HEAL_AMOUNT)


def cast_lightning():
    """ Cast lightning bolt to the closest monster in FOV

    """
    monster = closest_monster(LIGHTNING_RANGE)
    if not monster:
        message('No enemy is close enough to strike.', libtcod.red)
        return 'cancelled'

    message('A lightning bolt strikes the {} with a loud thunder! The damage '
            'is {} hit points.'.format(monster.name, LIGHTNING_DAMAGE))
    monster.fighter.take_damage(LIGHTNING_DAMAGE)


def cast_fireball():
    """ Cast a fireball to a targeted tile in FOV and burn all monsters
        including the player.

    """
    global objects

    message('Left-click a target tile for the fireball, or right-click to '
            'cancel.', libtcod.light_cyan)
    x, y = target_tile()
    if x is None:
        return 'cancelled'

    message('The fireball explodes, burning everything within {} '
            'tiles!'.format(FIREBALL_RADIUS), libtcod.orange)

    for obj in objects:
        if obj.distance(x, y) <= FIREBALL_RADIUS and obj.fighter:
            message('The {} gets burned for {} hit points.'.format(
                    obj.name, FIREBALL_DAMAGE), libtcod.orange)
            obj.fighter.take_damage(FIREBALL_DAMAGE)


def cast_confuse():
    """ Cast confusion to the closest monster in FOV

    """
    global objects

    message('Left-click an enemy to confuse it, or right-click to cancel.',
            libtcod.light_cyan)
    monster = target_monster(CONFUSE_RANGE)
    if not monster:
        return 'cancelled'

    old_ai = monster.ai
    monster.ai = ConfusedMonster(old_ai)
    monster.ai.owner = monster
    message('The eyes of the {} look vacant as it starts to stumble '
            'around!'.format(monster.name), libtcod.light_green)


def player_death(player):
    """ Death function for the player.

    """
    global game_state
    message('You died!', libtcod.red)
    game_state = 'dead'

    # Transform the player into a bloody corpse!
    player.char = '%'
    player.color = libtcod.dark_red


def monster_death(monster):
    """ Death function for the monster.

    """
    message('The {} is dead! You gain {} experience points.'.format(
            monster.name.capitalize(), monster.fighter.xp), libtcod.orange)
    monster.char = '%'
    monster.color = libtcod.dark_red
    monster.blocks = False
    monster.fighter = None
    monster.ai = None
    monster.name = 'remains of {}'.format(monster.name)
    monster.send_to_back()


def menu(header, options, width):
    """ Generic menu builder.

    Defines a list of options to the player.

    """
    global con
    global key

    if len(options) > 26:
        # Make sure we don't get carried away with the menu.
        raise ValueError('Cannot have a menu with more than 26 options.')

    # Calculate total height for the header (after auto-wrap) and one line per
    # option.
    header_height = libtcod.console_get_height_rect(con, 0, 0, width,
                                                    SCREEN_HEIGHT, header)
    if not len(header):
        header_height = 0
    height = len(options) + header_height

    # Create an off-screen console that represents the menu's window
    window = libtcod.console_new(width, height)

    # Print the header, with auto-wrap
    libtcod.console_set_default_foreground(window, libtcod.white)
    libtcod.console_print_rect_ex(window, 0, 0, width, height,
                                  libtcod.BKGND_NONE, libtcod.LEFT, header)

    # Print all the options
    y = header_height
    letter_index = ord('a')
    for option_text in options:
        text = '({}) {}'.format(chr(letter_index), option_text)
        libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE,
                                 libtcod.LEFT, text)
        y += 1
        letter_index += 1

    # Blit the contents of the "window" to the main screen
    x = SCREEN_WIDTH / 2 - width / 2
    y = SCREEN_HEIGHT / 2 - height / 2
    libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)

    # Present the mains screen to the player and wait for a key-press
    libtcod.console_flush()

    # Watch out for key presses and return the options index.
    key = libtcod.console_wait_for_keypress(True)

    if key.vk == libtcod.KEY_ENTER and key.lalt:
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())

    index = key.c - ord('a')
    if index >= 0 and index < len(options):
        return index
    return None


def inventory_menu(header):
    """ Creates the inventory menu

    """
    global inventory

    # show an menu with each item of the inventory as an option
    if not len(inventory):
        options = ['Inventory is empty.']
    else:
        options = [item.name for item in inventory]

    index = menu(header, options, INVENTORY_WIDTH)
    if index is None or not len(inventory):
        return None
    return inventory[index].item


def handle_keys():
    """ Handle key input from the user.

    """
    global game_state, key, objects, player, stairs

    if key.vk == libtcod.KEY_ENTER and key.lalt:
        # Alt+Enter: Toggles fullscreen
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
    elif key.vk == libtcod.KEY_ESCAPE:
        # Exit the game
        return 'exit'

    # movement
    if game_state == 'playing':
        key_char = chr(key.c)

        if key.vk == libtcod.KEY_UP or key_char == 'k':
            player_move_or_attack(0, -1)
        elif key.vk == libtcod.KEY_DOWN or key_char == 'j':
            player_move_or_attack(0, 1)
        elif key.vk == libtcod.KEY_LEFT or key_char == 'h':
            player_move_or_attack(-1, 0)
        elif key.vk == libtcod.KEY_RIGHT or key_char == 'l':
            player_move_or_attack(1, 0)
        elif key_char == 'y':
            player_move_or_attack(-1, -1)
        elif key_char == 'u':
            player_move_or_attack(1, -1)
        elif key_char == 'b':
            player_move_or_attack(-1, 1)
        elif key_char == 'n':
            player_move_or_attack(1, 1)
        else:
            # test for other keys
            if key_char == '.':
                message('pass', libtcod.violet)
                return 'pass-turn'
            if key_char == 'g':
                # pick up an item
                for obj in objects:
                    if obj.x == player.x and obj.y == player.y and obj.item:
                        obj.item.pick_up()
                        break
            if key_char == 'i':
                # show the inventory
                chosen_item = inventory_menu('Press the key next to an item '
                                             'to use it, or any key to cancel.'
                                             '\n')
                if chosen_item:
                    chosen_item.use()
            if key_char == 'd':
                # show the inventory
                chosen_item = inventory_menu('Press the key next to an item '
                                             'to drop it, or any key to '
                                             'cancel.\n')
                if chosen_item:
                    chosen_item.drop()
            if key_char == '<':
                # go down the stairs, if the player is on top of one.
                if stairs.x == player.x and stairs.y == player.y:
                    next_level()
            if key_char == 'c':
                # show character info
                level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
                msg = ('Character information\n\nLevel: {}\nExperience: {}\n'
                       'Experience to level up: {}\n\nMax HP: {}\nAttack: {}\n'
                       'Defense: {}').format(player.level, player.fighter.xp,
                                             level_up_xp,
                                             player.fighter.max_hp,
                                             player.fighter.power,
                                             player.fighter.defense)
                msgbox(msg, CHARACTER_SCREEN_WIDTH)

            return 'didnt-take-turn'


def get_names_under_mouse():
    """ Return a string of the names of the objects under the mouse and within
        FOV.

    """
    global mouse

    x, y = (mouse.cx, mouse.cy)
    names = [o.name for o in objects
             if o.x == x and o.y == y and in_fov(o.x, o.y)]
    names = ', '.join(names)
    return names.capitalize()


def message(new_msg, color=libtcod.white):
    global game_msgs

    new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)

    for line in new_msg_lines:
        # if buffer is full, remove the first line and make room for new msgs.
        if len(game_msgs) == MSG_HEIGHT:
            game_msgs.pop(0)

        # add the new line as a tuple with text and color
        game_msgs.append((line, color))


def render_all():
    """ Draw the game objects and the map.

    """
    global con, map, fov_recompute, fov_map, objects, player, panel,\
           dungeon_level

    # Recompute the FOV and reset the flag when the player moves.
    if fov_recompute:
        fov_recompute = False
        libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS,
                                FOV_LIGHT_WALLS, FOV_ALGO)

    # Go through all the tiles and set their color
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            visible = in_fov(x, y)
            wall = map[x][y].block_sight

            # Use the global dark or light colors depending on the visibility
            # of the tile. We also hide it until the player has explored it.
            if not visible:
                if map[x][y].explored:
                    if wall:
                        libtcod.console_set_char_background(con, x, y,
                                                            color_dark_wall,
                                                            libtcod.BKGND_SET)
                    else:
                        libtcod.console_set_char_background(con, x, y,
                                                            color_dark_ground,
                                                            libtcod.BKGND_SET)
            else:
                if wall:
                    libtcod.console_set_char_background(con, x, y,
                                                        color_light_wall,
                                                        libtcod.BKGND_SET)
                else:
                    libtcod.console_set_char_background(con, x, y,
                                                        color_light_ground,
                                                        libtcod.BKGND_SET)
                map[x][y].explored = True

    # Place the game objects on the off-screen and draw the player last.
    for obj in objects:
        if obj != player:
            obj.draw()
    player.draw()

    # Blit the contents of the off-screen to the main screen
    libtcod.console_blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)

    # Prepare the render the GUI panel
    libtcod.console_set_default_background(panel, libtcod.black)
    libtcod.console_clear(panel)

    # Print the game messages one line at a time.
    y = 1
    for (line, color) in game_msgs:
        libtcod.console_set_default_foreground(panel, color)
        libtcod.console_print_ex(panel, MSG_X, y, libtcod.BKGND_NONE,
                                 libtcod.LEFT, line)
        y += 1

    # Show the player's stats
    render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp,
               libtcod.light_red, libtcod.darker_red)

    # Show the dungeon level
    libtcod.console_print_ex(panel, 1, 3, libtcod.BKGND_NONE, libtcod.LEFT,
                             'Dungeon level {}'.format(dungeon_level))

    # Display names of objects under the mouse.
    libtcod.console_set_default_foreground(panel, libtcod.light_gray)
    libtcod.console_print_ex(panel, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT,
                             get_names_under_mouse())

    # Blit the contents of the panel to the main screen
    libtcod.console_blit(panel, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0,
                         PANEL_Y)


def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
    """ Generic status bar renderer.

    Can be used for health bar, mana bar, experience bar, dungeon level, etc.

    """
    global panel

    # determine the width of the bar to render.
    bar_width = int(float(value) / maximum * total_width)

    # render the background bar.
    libtcod.console_set_default_background(panel, back_color)
    libtcod.console_rect(panel, x, y, total_width, 1, False,
                         libtcod.BKGND_SCREEN)

    # render the foreground bar.
    libtcod.console_set_default_background(panel, bar_color)
    if bar_width > 0:
        libtcod.console_rect(panel, x, y, bar_width, 1, False,
                             libtcod.BKGND_SCREEN)

    # render some centered text with the values
    msg = '{}: {}/{}'.format(name, value, maximum)
    libtcod.console_set_default_foreground(panel, libtcod.white)
    libtcod.console_print_ex(panel, x + total_width / 2, y, libtcod.BKGND_NONE,
                             libtcod.CENTER, msg)


def msgbox(text, width=50):
    """ Uses the menu() as message box

    """
    menu(text, [], width)


def main_menu():
    """ Game main menu

    """
    img = libtcod.image_load('menu_background.png')
    title = 'Rumble in the Underdeep'
    author = 'By @cr8ivecodesmith'

    while not libtcod.console_is_window_closed():
        # blit the bg image at twice the regular console resolution
        libtcod.image_blit_2x(img, 0, 0, 0)

        libtcod.console_set_default_foreground(0, libtcod.gold)
        libtcod.console_print_ex(0, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 4,
                                 libtcod.BKGND_NONE, libtcod.CENTER, title)
        libtcod.console_print_ex(0, SCREEN_WIDTH / 2, SCREEN_HEIGHT - 2,
                                 libtcod.BKGND_NONE, libtcod.CENTER, author)

        # show the options and wait for the player's input
        choice = menu('', ['New game', 'Continue', 'Quit'], 24)

        if choice == 0:  # New game
            new_game()
            play_game()
        elif choice == 1:
            try:
                load_game()
                play_game()
            except Exception as e:
                print(e)
                msgbox('\nNo saved game to load.\n', 24)
                continue
        elif choice == 2:  # Quit
            break


def save_game():
    """ Saves the game

    There's a quirk here in that when more than one variable references the
    same object, shelve with store a copy of the object resulting in duplicated
    entry.

    This is the case if we keep the `player` object seperately since the same
    object is also referenced in the `objects` object. To overcome this, we
    just store the index of the `player` object in the `objects` list.

    """
    global map, objects, player, inventory, game_msgs, game_state,\
           dungeon_level, stairs

    file = shelve.open('savegame', 'n')
    file['map'] = map
    file['objects'] = objects
    file['player_index'] = objects.index(player)
    file['stairs_index'] = objects.index(stairs)
    file['inventory'] = inventory
    file['game_msgs'] = game_msgs
    file['game_state'] = game_state
    file['dungeon_level'] = dungeon_level
    file.close()


def load_game():
    """ Loads the game

    """
    global map, objects, player, inventory, game_msgs, game_state,\
           dungeon_level, stairs

    file = shelve.open('savegame', 'r')
    map = file['map']
    objects = file['objects']
    player = objects[file['player_index']]
    stairs = objects[file['stairs_index']]
    inventory = file['inventory']
    game_msgs = file['game_msgs']
    game_state = file['game_state']
    dungeon_level = file['dungeon_level']
    file.close()

    initialize_fov()


def next_level():
    """ Advance to the next level

    """
    global player, dungeon_level
    message('You take a moment to rest, and recover your strength.',
            libtcod.light_violet)
    player.fighter.heal(player.fighter.max_hp / 2)  # heals by 50% of max_hp

    message('After a rare moment of peace, you descend deeper into the heart '
            'of the Underdeep...', libtcod.red)

    dungeon_level += 1
    make_map()
    initialize_fov()


def make_map():
    """ Generates the map coordinates

    Room generation logic:
    Pick a random location for the first room and carve it. Then pick another
    location for the second; if it doesn't overlap with the first. Connect the
    two with a tunnel. Repeat.

    """
    global map, player, objects, stairs

    # Init list of game objects.
    objects = [player]

    # Fill map with unblocked tiles
    # Access the map: map[x][y]
    map = [[Tile(True) for y in range(MAP_HEIGHT)]
           for x in range(MAP_WIDTH)]

    rooms = []
    num_rooms = 0
    for r in range(MAX_ROOMS):
        # Random width and height
        w = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        h = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)

        # Random pos without going out of map boundaries
        x = libtcod.random_get_int(0, 0, MAP_WIDTH - w - 1)
        y = libtcod.random_get_int(0, 0, MAP_HEIGHT - h - 1)

        new_room = Rect(x, y, w, h)

        # Check if the other rooms intersect with this room.
        failed = False
        for other_room in rooms:
            if new_room.intersect(other_room):
                failed = True
                break

        if not failed:
            # "paint" it to the map.
            create_room(new_room)

            # put objects in it such as monsters.
            place_objects(new_room)

            new_x, new_y = new_room.center()

            if num_rooms == 0:
                # If this is the first room, put the player in it.
                player.x, player.y = (new_x, new_y)
            else:
                # All rooms after the first connects to the previous room with
                # a tunnel.

                # Center coords of the previous room.
                prev_x, prev_y = rooms[num_rooms - 1].center()

                # Draw a coin (random 0 or 1)
                if libtcod.random_get_int(0, 0, 1) == 1:
                    # First move horizontally, then vertically.
                    create_h_tunnel(prev_x, new_x, prev_y)
                    create_v_tunnel(prev_y, new_y, new_x)
                else:
                    # Do the opposite.
                    create_v_tunnel(prev_y, new_y, prev_x)
                    create_h_tunnel(prev_x, new_x, new_y)

            # Finally append the new room to the list
            rooms.append(new_room)
            num_rooms += 1

    # create stairs at the center of the last room
    stairs = Object(new_x, new_y, '<', 'stairs', libtcod.white,
                    always_visible=True)
    objects.append(stairs)
    stairs.send_to_back()


def initialize_fov():
    """ Create the FOV map according to the generated map.

    """
    global fov_recompute, fov_map, con

    fov_recompute = True

    libtcod.console_clear(con)

    # Initalize the FOV map.
    fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            libtcod.map_set_properties(fov_map, x, y,
                                       not map[x][y].block_sight,
                                       not map[x][y].blocked)


def new_game():
    """ Initalize variables on a new game

    """
    global player, inventory, game_msgs, game_state, dungeon_level

    game_state = 'playing'
    inventory = []
    game_msgs = []

    # Create the object representing the player.
    fighter_component = Fighter(hp=30, defense=2, power=5, xp=0,
                                death_function=player_death)
    player = Object(0, 0, '@', 'player', libtcod.white, blocks=True,
                    fighter=fighter_component)
    player.level = 1

    # Generate map coordinates.
    dungeon_level = 1
    make_map()

    # Set the welcome message.
    message('Welcome stranger! Seek your glory and prepare to perish in the '
            'mysterious Underdeep.', libtcod.red)

    # Initialize the FOV
    initialize_fov()


def play_game():
    global key, mouse, player_action

    player_action = None
    key = libtcod.Key()
    mouse = libtcod.Mouse()

    while not libtcod.console_is_window_closed():
        # Check for mouse of key press events
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS |
                                    libtcod.EVENT_MOUSE, key, mouse)
        # Render the screen.
        render_all()

        libtcod.console_flush()

        # Check for player level up
        check_level_up()

        # Clear characters on the off-screen
        for obj in objects:
            obj.clear()

        # handle keys and exit the game if needed
        player_action = handle_keys()

        if player_action == 'exit':
            save_game()
            break

        # Let monsters take their turn
        if (
            game_state == 'playing' and player_action != 'didnt-take-turn' or
            player_action == 'pass-turn'
        ):
            for obj in objects:
                if obj.ai:
                    obj.ai.take_turn()


if __name__ == '__main__':
    """ Initialization of required variables and game loop.

    """
    global con
    global panel

    # Set the font.
    libtcod.console_set_custom_font('terminal10x10.png',
                                    libtcod.FONT_TYPE_GREYSCALE |
                                    libtcod.FONT_LAYOUT_TCOD)

    # Init the main screen.
    libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT,
                              'pyroguecod tutorial', False)

    # Init an off-screen console to be used as a buffer.
    con = libtcod.console_new(SCREEN_WIDTH, SCREEN_HEIGHT)

    # Set FPS. This does not have an effect for turn-based games.
    libtcod.sys_set_fps(LIMIT_FPS)

    # Init the status bar console panel.
    panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)

    main_menu()
