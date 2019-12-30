import sink_settings as sinkSettings
import websocket
import kazoo
import time
import json
import math
import queue
import uuid
import os
import glob
import gzip
import ssl
import pathlib
from b2sdk.v1 import *
try:
    import thread
except ImportError:
    import _thread as thread

def construct_subscription(binding, auth_token, account_id):
    return json.dumps({'action': 'subscribe', 'auth_token': auth_token,
                       'data': {'account_id': account_id, 'binding': binding}})


def on_message(ws, message):
    try:
        json_dec = json.loads(message)
        if 'data' in json_dec:
            if 'subscribed' not in json_dec['data']:
                print(json.dumps(json_dec))
                file_queue.put(json.dumps(json_dec))
        else:
            print(message)
            file_queue.put(message)
    except:
        print(message)
        file_queue.put(message)


def on_error(ws, error):
    print(error)


def on_close(ws):
    print("### socket closed ###")


def on_open(ws):
    def run(*args):
        for account in account_subs:
            for sub in event_subs:
                ws.send(construct_subscription(sub, account['auth_token'], account['account_id']))
                time.sleep(1/rate_limit_per_second)

    thread.start_new_thread(run, ())


def closer(minutes):
    time.sleep(minutes*60)
    global closing_time
    closing_time = True
    ws.close()


def old_file_cleanup():
    # Cleans up old socketsink files if they weren't uploaded atexit for some reason
    global run_time
    # select all files ending with .socketsink and sort them by modified datetime
    files = glob.glob("*.socketsink.gz")
    files.sort(key=os.path.getmtime)

    for file in files:
        # break loop if current file is not at least 2x as old at the run_time (prevents write locks)
        # *180 used instead of *3 because runtime is in minutes not seconds
        if time.time() - (run_time * 180) < os.path.getmtime(file):
            break
        b2_file_upload(file)


def b2_file_upload(file):
    info = InMemoryAccountInfo()
    b2_api = B2Api(info)
    application_key_id = sinkSettings.bz_application_key_id
    application_key = sinkSettings.bz_application_key
    b2_api.authorize_account("production", application_key_id, application_key)
    bucket = b2_api.get_bucket_by_name(sinkSettings.bz_bucket_name)
    try:
        bucket.upload_local_file(local_file=file, file_name=(sinkSettings.bz_unprocessed_folder_name + file))
        os.remove(file)
    except:
        pass


def cleanup():
    ws.close()
    # saves all items in queue to a file with the name like StartTimeAsUNIXTimeStamp_UUID.socketsink
    # UUID is used in case sinks are being run on multiple machines
    file_name = str(start_time) + "_" + str(uuid.uuid1()) + ".socketsink.gz"
    file_contents = ''
    while not file_queue.empty():
        file_contents += (file_queue.get() + '\n')

    with gzip.open(file_name, 'wb') as log:
        log.write(file_contents.encode('utf-8'))

    # Upload it to Backblaze B2
    b2_file_upload(file_name)


if __name__ == "__main__":
    start_time = time.time()

    # Transactions per second rate limit (int)(transactions/second)
    rate_limit_per_second = 10

    # Run Time (int)(minutes)
    # This script is engineered to only run for a set time. For an hour for example
    # Then, presumably a new instance will be started by cron
    run_time = 30

    # Accounts to subscribe to
    # If sub_descendants exists and is true, all sub-accounts will also be subscribed to
    account_subs = sinkSettings.accounts_to_sub

    # Events to subscribe to for each account
    event_subs = sinkSettings.events_to_sub

    # Variable to track when the script is intentionally closing itself down
    closing_time = False

    # Queue used to collect events to later dump to a file
    file_queue = queue.Queue()

    descendant_accounts_to_append = []

    # Populate auth_tokens for all accounts
    for account in account_subs:
        kaz_client = kazoo.Client(base_url=sinkSettings.api_base_url, api_key=account['api_key'])
        kaz_client.authenticate()
        account['auth_token'] = kaz_client.auth_token
        # Populate decendant accounts with same auth token as the master account
        if account.get('sub_descendants', False):
            decendents = kaz_client.get_account_descendants(account['account_id']).get('data', {})
            for descendant in decendents:
                descendant_accounts_to_append.append({'account_id': descendant['id'],
                                                      'auth_token': kaz_client.auth_token})

    # Add the descendent accounts to the main list of subscriptions
    account_subs = account_subs + descendant_accounts_to_append

    # Delete the descendant_accounts_to_append since it's no longer needed
    del descendant_accounts_to_append

    # Calculating spin_up_time: Below we have the total number of transactions we'll need to issue
    spin_up_time = len(account_subs) * len(event_subs)
    # Calculating spin_up_time: Below we have divided the number of transactions by the rate/second
    # giving us seconds for spin up
    spin_up_time = spin_up_time/rate_limit_per_second
    # Calculating spin_up_time: Now, we divide by 60 to get the total number of minutes needed to spin up
    spin_up_time = spin_up_time/60
    # Multiplying by 5 so that we can grow 5x each iteration without losing any data
    spin_up_time = spin_up_time*5
    # Calculating spin_up_time: rounding up to the nearest int
    spin_up_time = math.ceil(spin_up_time)

    # Starts a thread that will close down the script after so many minutes
    # The currently calculated spin up time * 5 is added to provide a little overlap
    # for the new instance to connect and subscribe
    # duplicate records aren't a problem, missing ones are though
    # So long as we don't grow more then 5x in a single run of the instance, this should provide enough
    # extra time at the end for the next iteration to spin up
    thread.start_new_thread(closer, (run_time+spin_up_time,))

    # Starts a thread to upload old socketsink files to backblaze
    thread.start_new_thread(old_file_cleanup, ())

    while not closing_time:
        ws = websocket.WebSocketApp(sinkSettings.ws_base_url,
                                    on_message=on_message,
                                    on_close=on_close)
        ws.on_open = on_open

        ws.run_forever(sslopt=dict(ca_certs=sinkSettings.ca_pem))

        # Sleeps for 5 seconds if it's not closing time
        # This allows for a small time-out if the connection unexpectedly closes
        if not closing_time:
            time.sleep(5)

    cleanup()
