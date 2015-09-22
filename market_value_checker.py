# Made by Solax from the Toribash community for the community

import json
import hashlib
import requests
import time
from collections import defaultdict
import datetime

session = requests.Session()
BASE_URL = 'http://forum.toribash.com/'

timeout = 1.0


# Gets the timestamp to be the name of our output file
def timeStamped(fname, fmt='%Y-%m-%d-%H-%M-%S_{fname}'):
    return datetime.datetime.now().strftime(fmt).format(fname=fname)


# Code to get the user to provide login details to get a token
def loginPart(theSession):
    # global session
    # global token
    username = raw_input("Enter your username \
(of the account to do the market crawling): ")
    password = raw_input("Enter your password \
(of the account to do the market crawling): ")
    try:
        theSession.post(
            BASE_URL +
            'login.php?do=login', {
                'vb_login_username':
                    username,
                'vb_login_password':
                    '',
                'vb_login_md5password':
                    hashlib.md5(password.encode()).hexdigest(),
                'vb_login_md5password_utf':
                    hashlib.md5(password.encode()).hexdigest(),
                'cookieuser':
                    1,
                'do':
                    'login',
                's':
                    '',
                'securitytoken':
                    'guest'
            }
        )
        token = theSession.get(
            BASE_URL +
            'bank_ajax.php?bank_ajax=get_token'
        ).json()['token']
        return token
    except KeyError:
        print "Failed to login. Please enter your details again."
        print
        loginPart(theSession)


# Code to get the name of the user who's items we want to check
def userCheckInput():
    try:
        user_check = raw_input("Enter the username \
of the user to check the inventory for: ")
        session.get(
            "http://forum.toribash.com/tori_stats.php?username=" +
            user_check +
            "&format=json"
        ).json()
        return user_check
    except ValueError:
        print "That user is not registered. Please try again."
        print
        userCheckInput()


def outputWriter(number_owned, item_name, undercut, message):
    messages = [
        "on the market and can't be bought in shop with tc",
        "not on the market and can't be bought in shop with tc",
        "not on the market but can be bought in shop with tc",
        "on the market (cheaper) and can be bought in the shop with tc",
        "on the market and can be bought in the shop with tc (cheaper)"
    ]

    file.write(
        str(number_owned) +
        " - " +
        messages[message] +
        " - " +
        item_name +
        " - " +
        str(undercut) +
        " - " +
        str(number_owned * undercut) +
        "\n"
    )

    return undercut


# Code to check how much our undercut value is
def undercutFunct(store_price, stock, number_owned, cheapest_on_market):
        # If the item can't be bought in the shop for tc
        # (because it's either a 3d item or a collectable not buyable with
        # tc and/or it's a normal item out of stock)
        # then check the following cases.
        if store_price == 0 or stock == 0:
            # If it's already offered on the market
            # then we undercut that price by 1.
            if cheapest_on_market is not None:
                undercut = cheapest_on_market - 1
                return outputWriter(number_owned, item_name, undercut, 0)
            # If it's not in the market
            # then you can set whatever price you want.
            else:
                undercut = 0
                return outputWriter(number_owned, item_name, undercut, 1)

        # If it can be bought in the store for tc right now.
        elif store_price != 0 and stock != 0:

            # If the item is not on the market
            # then our undercut price is 1 below the shop price.
            if cheapest_on_market is None:
                undercut = store_price - 1
                return outputWriter(number_owned, item_name, undercut, 2)
            # If it is available in the market already then undercut
            # the cheapest of either the shop or market prices so you're
            # always offering the cheapest item
            else:
                if cheapest_on_market < store_price:
                    undercut = cheapest_on_market - 1
                    return outputWriter(number_owned, item_name, undercut, 3)

                else:
                    undercut = store_price - 1
                    return outputWriter(number_owned, item_name, undercut, 4)


# Functions for dictionary stuff
def counters():
    return defaultdict(int)


def freqs(LofD):
    r = defaultdict(counters)
    for d in LofD:
        for k, v in d.items():
            r[k][v] += 1
    return dict((k, dict(v)) for k, v in r.items())


token = loginPart(session)
user_to_check = userCheckInput()

items = []
offset = 0

# Get a list of all of the items for sale - aka market items
print "Working on it..."

while True:
    data = session.get(BASE_URL + 'bank_ajax.php', params={
        'bank_ajax': 'get_inventory',
        'username': user_to_check,
        'offset': offset,
        'token': token
    }).json()
    offset += data['inventory']['max_items_per_request']

    items.extend(
        i for i in data['inventory']['items'] if
        i['is_for_sale'] and not
        i['is_set'] and not
        i['setid']
    )
    if offset > data['inventory']['total_user_items']:
        break

    # Now we have a list of the names of all the market items of the user

print "Still working..."

item_names = {
    i['item_name'] for i in items
}

total_items = len(items)

item_prices = session.get(
    'http://forum.toribash.com/ingame_store.php?json'
).json()

sum_value = 0
done = 0

file = open(
    timeStamped(
        user_to_check +
        '_market_check.txt'
    ),
    'w'
)

file.write(
    "Number owned - status - item name - price to be put on market for \
- total value for item type\n"
)


# Go through every type of item in the inventory
# and check it for what price it should be when undercut.

for item_name in item_names:
    start_time = time.time()
    item_data = session.get(
        BASE_URL +
        'tori_market.php',
        params={
            'action':
                'search',
            'item':
                item_name,
            'format':
                'json'
        }
    ).json()

    number_owned = freqs(items).get('item_name').get(item_name)

    # This line is important because we don't want
    # to undercut the user's own items.
    item_data['items'] = [
        i for i in item_data['items'] if
        i['username'].lower() != user_to_check
    ]

    # The priority option is to grab the item's info from the
    # /ingame_store.php?json page but not all items are there.
    # Still though, try this first. We have a backup bellow
    # if it fails.
    try:
        store_price = next(
            (
                item for item in item_prices if item["itemname"] == item_name
            ),
            None)['price']
        stock = next(
            (
                item for item in item_prices if item["itemname"] == item_name
            ),
            None)['stock']
    except TypeError:
        # If it wasn't there then just keep going
        pass

    cheapest_on_market = None

    # If this specific item is on the market
    # then extract its cheapest market price
    # And also extract info about the stock
    # and shop price in case the above attempt failed.
    # If it overwrites the above then no matter
    # because the info should be the same for the purpose here.
    if item_data['items']:
        item = item_data['items'][0]
        store_price = item['store_price']

        if item['out_of_stock']:
            stock = 0
        else:
            stock = 1
        # The cheapest price is the price of the cheapest one available.
        cheapest_on_market = item['price']

    undercut = None
    undercut = undercutFunct(
        store_price,
        stock,
        number_owned,
        cheapest_on_market
    )
    # Accumulate the value of all the item values as we go.
    sum_value += number_owned * undercut
    # Keep a continuous output going of where we are up to
    # in temrs of all items since this program can take a while to run.
    done += number_owned
    print (
        "Completed " +
        str(done) +
        " out of a total of " +
        str(total_items) +
        " items."
    )
    # Wait for one second so we don't get banned for overusing the market
    finishtime = time.time() - start_time

    # If it has been shorter than 1 second since the market was called
    # then we only need to wait for however long will get us to that 1s.
    # 0.01 is added in for safety.
    if finishtime < 1:
        time.sleep(timeout - finishtime + 0.01)

file.write(
    "Your total marketable value \
(not including items not in stock or in the market) is equal to: " +
    str(sum_value)
)
file.close()

print "Finished"
raw_input("Press Enter to exit")
