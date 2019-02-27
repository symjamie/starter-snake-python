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

    color = "#00FF00"

    return start_response(color)


# Currently only work for a length of 3.
def self_loop(data):
    my_body = data["you"]["body"]
    my_head = my_body[0]
    my_neck = my_body[1]
    if my_head["x"] == my_neck["x"] and my_head["y"] == my_neck["y"]:
        return
    if my_head["x"] > my_neck["x"]:
        last_move = "right"
    elif my_head["x"] < my_neck["x"]:
        last_move = "left"
    elif my_head["y"] < my_neck["y"]:
        last_move = "up"
    elif my_head["y"] > my_neck["y"]:
        last_move = "down"
    directions = ['up', 'right', 'down', 'left']
    idx = directions.index(last_move)
    direction = directions[(idx+1)%4]
    return direction


def deadend(data, path, you_body, depth):
    if depth == 3:
        return False

    steps = len(path)-1
    blocked = []
    for snake in data["board"]["snakes"]:
        if snake == data["you"]:
            continue
        body = snakes["body"]
        # Their body will move away after these steps.
        if len(body) <= steps:
            continue
        else:
            body = body[:-steps]
        for cell in snakes["body"]:
            blocked += [(cell["x"], cell["y"])]

    # Your body after eating the target food.
    you_body = (list(reversed(path[1:])) + you_body)[:-(steps+1)]
    blocked += you_body[1:]

    #print("blocked: {}".format(blocked))

    graph = Graph()
    #print("Edges: ", end="")
    for x in range(0, data["board"]["width"]):
        for y in range(0, data["board"]["height"]):
            if (x, y) in blocked:
                continue
            if (x+1, y) not in blocked and x != data["board"]["width"]-1:
                graph.add_edge((x, y), (x+1, y), {'cost': 1})
                graph.add_edge((x+1, y), (x, y), {'cost': 1})
                #print("({}, {})-({}, {}) ".format(x, y, x+1, y), end="")
            if (x, y+1) not in blocked and y != data["board"]["height"]-1:
                graph.add_edge((x, y), (x, y+1), {'cost': 1})
                graph.add_edge((x, y+1), (x, y), {'cost': 1})
                #print("({}, {})-({}, {}) ".format(x, y, x, y+1), end="")
    #print()
    cost_func = lambda u, v, e, prev_e: e['cost']

    head = you_body[0]
    foods = {}
    for food in data["board"]["food"]:
        key = (food["x"], food["y"])
        foods[key] = abs(head[0] - food["x"]) + abs(head[1] - food["y"])
    foods_sorted = sorted(foods.items(), key=operator.itemgetter(1))

    # Skip the nearest ones that have been eaten.
    for food in foods_sorted[depth:]:
        # If the nearest food can not be reached, go for the next nearest one.
        try:
            nodes = find_path(graph, head, food[0], cost_func=cost_func).nodes
            print("Can still go for food {}.".format(food[0]))
            return deadend(data, nodes, you_body, depth+1)
        except Exception:
            continue
    return True


def dijkstra(data):
    blocked = []
    for snake in data["board"]["snakes"]:
        if snake == data["you"]:
            continue
        for cell in snakes["body"]:
            blocked += [(cell["x"], cell["y"])]
    you_body = []
    for cell in data["you"]["body"]:
        you_body += [(cell["x"], cell["y"])]
    blocked += you_body[1:]

    graph = Graph()
    #print("Edges: ", end="")
    for x in range(0, data["board"]["width"]):
        for y in range(0, data["board"]["height"]):
            if (x, y) in blocked:
                continue
            if (x+1, y) not in blocked and x != data["board"]["width"]-1:
                graph.add_edge((x, y), (x+1, y), {'cost': 1})
                graph.add_edge((x+1, y), (x, y), {'cost': 1})
                #print("({}, {})-({}, {}) ".format(x, y, x+1, y), end="")
            if (x, y+1) not in blocked and y != data["board"]["height"]-1:
                graph.add_edge((x, y), (x, y+1), {'cost': 1})
                graph.add_edge((x, y+1), (x, y), {'cost': 1})
                #print("({}, {})-({}, {}) ".format(x, y, x, y+1), end="")
    #print()
    cost_func = lambda u, v, e, prev_e: e['cost']

    head = you_body[0]
    foods = {}
    for food in data["board"]["food"]:
        key = (food["x"], food["y"])
        foods[key] = abs(head[0] - food["x"]) + abs(head[1] - food["y"])
    foods_sorted = sorted(foods.items(), key=operator.itemgetter(1))

    for food in foods_sorted:
        # If the nearest food can not be reached, go for the next nearest one.
        try:
            nodes = find_path(graph, head, food[0], cost_func=cost_func).nodes
            print("Going for food {}.".format(food[0]))
            if deadend(data, nodes, you_body, 1):
                print("Dead-end.")
                continue
            else:
                next_block = nodes[1]
                if head[0] == next_block[0] and head[1] > next_block[1]:
                    return "up"
                elif head[0] == next_block[0] and head[1] < next_block[1]:
                    return "down"
                elif head[0] < next_block[0] and head[1] == next_block[1]:
                    return "right"
                else:
                    return "left"
        except Exception:
            continue

    # ..Where do we go now?
    print("Who am I? Where am I?")
    return False


@bottle.post('/move')
def move():
    data = bottle.request.json

    """
    TODO: Using the data from the endpoint request object, your
            snake AI must choose a direction to move in.
    """

    #print(json.dumps(data))

    # The dumbest way...
    #return move_response(self_loop(data))

    # Avoid being killed.

    # Kill snake in parallel.

    # Go for a food.
    direction = dijkstra(data)

    #print(direction)
    return move_response(direction)


@bottle.post('/end')
def end():
    data = bottle.request.json

    """
    TODO: If your snake AI was stateful,
        clean up any stateful objects here.
    """
    print(json.dumps(data))

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
