import json
import os
import random
import bottle

from api import ping_response, start_response, move_response, end_response

from dijkstar import Graph, find_path
import operator

@bottle.route('/')
def index():
    return '''
    Battlesnake documentation can be found at
       <a href="https://docs.battlesnake.io">https://docs.battlesnake.io</a>.
    '''

@bottle.route('/static/<path:path>')
def static(path):
    """
    Given a path, return the static file located relative
    to the static folder.

    This can be used to return the snake head URL in an API response.
    """
    return bottle.static_file(path, root='static/')

@bottle.post('/ping')
def ping():
    """
    A keep-alive endpoint used to prevent cloud application platforms,
    such as Heroku, from sleeping the application instance.
    """
    return ping_response()

@bottle.post('/start')
def start():
    data = bottle.request.json

    """
    TODO: If you intend to have a stateful snake AI,
            initialize your snake state here using the
            request's data if necessary.
    """
    #print(json.dumps(data))

    color = "#00FFFF"

    return start_response(color)


def head2head(data):
    body_you = data["you"]["body"]
    head_you = body_you[0]
    hitpoints = []
    for snake in data["board"]["snakes"]:
        body = snake["body"]
        head = body[0]
        win = len(body_you) > len(body)
        if win:
            continue
        # Distance of 2.
        # Horizontal.
        if abs(head_you["x"]-head["x"]==2) and head_you["y"] == head["y"]:
            hitpoints += [int(((head_you["x"]+head["x"])/2), head["y"])]
        # Vertical.
        elif abs(head_you["y"]-head["y"]==2) and head_you["x"] == head["x"]:
            hitpoints += [(head["x"], int((head_you["y"]+head["y"])/2))]
        # Distance of sqrt(2).
        elif abs(head_you["x"]-head["x"]==1) and abs(head_you["y"]-head["y"]==1):
            hitpoints += [(head_you["x"], head["y"]), (head["x"], head_you["y"])]
        # Just look at one dangerous snake.
        if hitpoints != []:
            return hitpoints
    # Consider all dangerous snakes.
    return hitpoints


def make_graph(data, blocked):
    graph = Graph()
    #print("Edges: ", end="")
    for x in range(0, data["board"]["width"]):
        for y in range(0, data["board"]["height"]):
            if (x, y) in blocked:
                continue
            if (x+1, y) not in blocked and x != data["board"]["width"]-1:
                graph.add_edge((x, y), (x+1, y), {'cost': 1})
                graph.add_edge((x+1, y), (x, y), {'cost': 1})
            if (x, y+1) not in blocked and y != data["board"]["height"]-1:
                graph.add_edge((x, y), (x, y+1), {'cost': 1})
                graph.add_edge((x, y+1), (x, y), {'cost': 1})
    return graph


# foods_eaten: list of food that will be eaten in the deadend test.
def deadend(data, path, you_body, foods_eaten, depth):
    if depth == 3:
        return False

    steps = len(path)-1
    blocked = []
    for snake in data["board"]["snakes"]:
        if snake == data["you"]:
            continue
        body = snake["body"]
        # Their body will move away after these steps.
        if len(body) <= steps:
            continue
        else:
            body = body[:-steps]
        for cell in snake["body"]:
            blocked += [(cell["x"], cell["y"])]

    # Your body after eating the target food.
    you_body = (list(reversed(path[1:])) + you_body)[:-steps]
    blocked += you_body[1:]
    head = you_body[0]
    tail = you_body[-1]
    cost_func = lambda u, v, e, prev_e: e['cost']

    # Test if it can still go for its tail.
    # You will EAT your own tail.
    if abs(head[0]-tail[0])+abs(head[1]-tail[1]) == 1:
        print("\tCannot go for tail at {} (head is next to tail).".format(tail))
    # Safe, remove tail from blocked.
    else:
        blocked1 = blocked[:-1]
        graph1 = make_graph(data, blocked1)
        try:
            nodes = find_path(graph1, head, tail, cost_func=cost_func).nodes
            print("\tCan still go for tail at {}.".format(tail))
            return False
        except Exception:
            print("\tCannot go for tail at {}.".format(tail))

    # Test if it can still go for the next food.
    graph = make_graph(data, blocked)
    foods = {}
    for food in data["board"]["food"]:
        key = (food["x"], food["y"])
        foods[key] = abs(head[0] - food["x"]) + abs(head[1] - food["y"])
    foods_sorted = sorted(foods.items(), key=operator.itemgetter(1))
    foods_sorted = [food[0] for food in foods_sorted]
    # Skip the foods that will been eaten.
    for food in foods_eaten:
        foods_sorted.remove(food)
    for food in foods_sorted:
        # If the nearest food can not be reached, go for the next nearest one.
        try:
            nodes = find_path(graph, head, food, cost_func=cost_func).nodes
            print("\tCan still go for food at {}.".format(food))
            return deadend(data, nodes, you_body, foods_eaten+[food], depth+1)
        except Exception:
            continue

    return True


# self_loop: go for the nearest food if false, else go for own tail.
def dijkstra(data, self_loop, hitpoints):
    blocked = hitpoints
    for snake in data["board"]["snakes"]:
        if snake == data["you"]:
            continue
        for cell in snake["body"]:
            blocked += [(cell["x"], cell["y"])]
    you_body = []
    for cell in data["you"]["body"]:
        you_body += [(cell["x"], cell["y"])]

    if not self_loop:
        blocked += you_body[1:]
    else:
        # Just ate a food.
        dist = abs(you_body[0][0] - you_body[-1][0]) + abs(you_body[0][1] - you_body[-1][1])
        if you_body[-1] == you_body[-2] and dist > 1:
            blocked += you_body[1:-2]
        else:
            blocked += you_body[1:-1]

    graph = make_graph(data, blocked)
    cost_func = lambda u, v, e, prev_e: e['cost']

    head = you_body[0]

    if not self_loop:
        foods = {}
        for food in data["board"]["food"]:
            key = (food["x"], food["y"])
            if key in hitpoints:
                continue
            foods[key] = abs(head[0] - food["x"]) + abs(head[1] - food["y"])
        foods_sorted = sorted(foods.items(), key=operator.itemgetter(1))
        foods_sorted = [food[0] for food in foods_sorted]

        direction = None
        for food in foods_sorted:
            # If the nearest food can not be reached, go for the next nearest one.
            try:
                nodes = find_path(graph, head, food, cost_func=cost_func).nodes
                print("Testing for food {}.".format(food))
                next_block = nodes[1]
                if head[0] == next_block[0] and head[1] > next_block[1]:
                    direction = "up"
                elif head[0] == next_block[0] and head[1] < next_block[1]:
                    direction = "down"
                elif head[0] < next_block[0] and head[1] == next_block[1]:
                    direction = "right"
                else:
                    direction = "left"
                if deadend(data, nodes, you_body, [food], 1):
                    print("Dead-end.")
                    continue
                else:
                    return direction
            # No path.
            except Exception as e:
                #print(e)
                continue

        if direction != None:
            return direction
        else:
            # ..Where do we go now?
            print("Who am I? Where am I?")
            return False

    else:
        tail = you_body[-1]
        try:
            nodes = find_path(graph, head, tail, cost_func=cost_func).nodes
            print("Going for tail at {}.".format(tail))
            #if deadend(data, nodes, you_body, 1):
            #    print("Dead-end.")
            #    continue
            #else:
            next_block = nodes[1]
            if head[0] == next_block[0] and head[1] > next_block[1]:
                return "up"
            elif head[0] == next_block[0] and head[1] < next_block[1]:
                return "down"
            elif head[0] < next_block[0] and head[1] == next_block[1]:
                return "right"
            else:
                return "left"
        except Exception as e:
            print("Can not find a way to own tail.")
            print(blocked)
            print(e)
            return False


def strech(data):
    body = data["you"]["body"]
    head = body[0]
    neck = body[1]
    if head["x"] == neck["x"] and head["y"] == neck["y"]:
        return "right"
    if head["x"] > neck["x"]:
        last_move = "right"
    elif head["x"] < neck["x"]:
        last_move = "left"
    elif head["y"] < neck["y"]:
        last_move = "up"
    elif head["y"] > neck["y"]:
        last_move = "down"
    directions = ['up', 'right', 'down', 'left']
    idx = directions.index(last_move)
    return directions[(idx+1)%4]


@bottle.post('/move')
def move():
    data = bottle.request.json

    """
    TODO: Using the data from the endpoint request object, your
            snake AI must choose a direction to move in.
    """

    #print(json.dumps(data))
    print("Snake: {},Turn: {}".format(data["you"]["name"], data["turn"]))

    hitpoints = head2head(data)
    if hitpoints != []:
        print("Hitpoints: {}".format(hitpoints))

    # Streching.
    if data["turn"] < 4:
        return move_response(strech(data))

    if data["you"]["health"] < 100:
        # Go for a food.
        direction = dijkstra(data, False, hitpoints)
        if direction == False:
            direction = dijkstra(data, True, hitpoints)

    else:
        direction = dijkstra(data, True, hitpoints)
        if direction == False:
            direction = dijkstra(data, False, hitpoints)

    #print(direction)
    return move_response(direction)


@bottle.post('/end')
def end():
    data = bottle.request.json

    """
    TODO: If your snake AI was stateful,
        clean up any stateful objects here.
    """
    #print(json.dumps(data))

    return end_response()

# Expose WSGI app (so gunicorn can find it)
application = bottle.default_app()


if __name__ == '__main__':
    bottle.run(
        application,
        host=os.getenv('IP', '0.0.0.0'),
        port=os.getenv('PORT', '8080'),
        debug=os.getenv('DEBUG', True)
    )
