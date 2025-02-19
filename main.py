# from accounts import getAccountInfo
import config
from db import create_session, setup_database
from dbWriteOperations import update_user_and_metrics, add_post, add_comments, checkout_user
from dbReadOperations import get_accounts_ready_to_scrape, get_post
from accounts import getAccountInfo, getAccountInfoAPI
from byVideo import get_video_and_comments
import os
from datetime import datetime
import pytz
import traceback
import time
import multiprocessing
import random
import traceback
from utils import wait_until_15_to_25_minutes


start_scrape_date = '2024-1-25'
# 28
end_scrape_date = '2024-1-28'
os.environ['end_scrape_date'] = end_scrape_date
os.environ['start_scrape_date'] = start_scrape_date

# display = Display(visible=0, size=(1366, 768))
# display.start()

def main():
    # img_block = random.choice([True, False])
    os.environ['img_block'] = str(False)
    img_block = False
    # print(img_block)
    # exit()
    config.SESS = create_session()
    print("Created Session")
    total_vids_scraped = 0
    total_comments_scraped = 0
    start_time = time.time()
    with config.SESS:
        config.BASE = setup_database(config.SESS)
        # table_names = config.BASE.classes.keys()
        # print("List of tables:")
        # for table_name in table_names:
        #     print(table_name)
        # exit()

        account = get_accounts_ready_to_scrape(end_scrape_date)
        print('Fetched account for scraping')
        while account:
            # int(len(accounts)/2)
            username = account.username
            # checkout_user(accounts[0].username, end_scrape_date)

            print(username)
            res = scrape_account(username, img_block)
            if res:
                total_vids_scraped += res[0]
                total_comments_scraped += res[1]
            else:
                print(f"Fail for {username}")
            account = get_accounts_ready_to_scrape(end_scrape_date)
    print(f'Finished at {time.time() - start_time}')
    print(f'Total videos scraped: {total_vids_scraped}')
    print(f'Total comments scraped: {total_comments_scraped}')

    print('main')

def worker_function_accounts(queue, *args):
    # queue.put((None, None))
    try:
        account_info, videos_to_scrape = getAccountInfoAPI(*args)
        queue.put((account_info, videos_to_scrape))
        time.sleep(0.5)
    except Exception as e:
        # Log or print the exception for debugging
        print(f"Error in worker_function_accounts: {e}")
        traceback.print_exc()
        queue.put((None, None))

def worker_function_videos(queue, *args):
    try:
        video_info, video_metrics, comment_data_list = get_video_and_comments(*args)
        queue.put((video_info, video_metrics, comment_data_list))
        time.sleep(0.5)
    except Exception as e:
        # Log or print the exception for debugging
        print(f"Error in worker_function_videos: {e}")
        queue.put((None, None, None))

def run_with_timeout(func, timeout, return_three, *args):
    queue = multiprocessing.Queue()
    process = multiprocessing.Process(target=func, args=(queue,) + args)
    process.start()
    process.join(timeout=timeout)
    print(func)
    print(timeout)
    print(return_three)
    if process.is_alive():
        print("Function ran too long, terminating it.")
        process.terminate()
        if return_three:
            return None, None, None
        return None, None  # Or some default values or raise an exception
    else:
        print('Ab to get')
        return queue.get()

def transform_input(value):
    if value >= 1100:
        return 600
    elif value <= 0:
        return 120
    else:
        # Linearly scale value to the range [120, 500]
        return int(120 + (value / 1100) * (600 - 120))

def scrape_account(username, img_block):
    
    for i in range(8):
        # time.sleep(random.randint(10, 35))
        try:
            account_info, videos_to_scrape = run_with_timeout(worker_function_accounts, 360, False, username, img_block)
            print(account_info)
            if account_info == None:
                # wait_until_15_to_25_minutes()
                print("Account info is none, time out, trying again")
                continue
            if not videos_to_scrape:
                print('No videos to scrape, trying again')
                continue
            deleted = 'account_deleted' in account_info
            private = 'account_private' in account_info
            if deleted:
                print("user deleted")
                update_user_and_metrics(username, account_info, end_scrape_date, deleted, private)
                return
            if private:
                print("user private")
                update_user_and_metrics(username, account_info, end_scrape_date, deleted, private)
                return

            if not len(videos_to_scrape) and account_info['num_posts'] != 0:
                print("No Videos to scrape, trying again")
                # wait_until_15_to_25_minutes()
                continue
            break
        except Exception as e:
            print(e)
            stacktrace_str = traceback.format_exc()
            print(stacktrace_str)
            if i == 6:
                time.sleep(100)
            if i == 7:
                print(f"Error getting {username} account info, giving up on try {i + 1}")
                return
            print(f"Error getting {username} account info, trying again")
            print(e)
            # wait_until_15_to_25_minutes()
            continue
    
    vids_stored = 0
    comments_scraped = 0
    videos_to_use = []
    if videos_to_scrape:
        
        print(f'{len(videos_to_scrape)} videos fetched')
        if len(videos_to_scrape):
            for v in videos_to_scrape:
                # wait_until_15_to_25_minutes()
                video_info, video_metrics = v
                # video_url = f'www.tiktok.com/@{username}/video/{v["id"]}'
                
                video_url = video_info['post_url']
                print(f'Trying to scrape {video_url}')
                print(f'Num comments is {video_metrics["num_comments"]}')
                utc = pytz.UTC
                compare_date = datetime.strptime(os.environ.get("end_scrape_date"), '%Y-%m-%d').replace(tzinfo=utc)
                if video_metrics["date_posted"] > compare_date:
                    print(f"Video: {video_url} is too new, skipping")
                    continue
                compare_date = datetime.strptime(os.environ.get("start_scrape_date"), '%Y-%m-%d').replace(tzinfo=utc)
                if video_metrics["date_posted"] < compare_date:
                    print(f"Video: {video_url} is too old, hit the end of the range")
                    break
                if get_post(video_url):
                    print("Already have this post")
                    continue
                videos_to_use.append((video_info['post_url'], video_metrics['num_comments']))
                print(f"Adding {video_info['post_url']} to ttposts")
                for i in range(3):
                    try:
                        res = add_post(video_info, video_metrics)
                        
                    except Exception as e:
                        if i == 2:
                            print('Last try failed, giving up')
                            break
                        stacktrace_str = traceback.format_exc()
                        print(stacktrace_str)
                        print(e)
                        print('trying again')
    for vid in videos_to_use:
        
        link, num_comments = vid
        print(f"Scraping comments for {link}")
        print(f'Num comments is {num_comments}')

        for i in range(3):
            vidStuf = get_video_and_comments(link, num_comments, img_block=img_block)
            print("here")
            if vidStuf[0] == None:
                print("Time out, trying again")
            else:
                break

        video_info, video_metrics, comment_data_list = vidStuf
        if video_info != None:
            print(f'{len(comment_data_list)} comments collected, adding comments to db')
            for i in range(3):
                try:
                    if len(comment_data_list):
                        add_comments(comment_data_list)
                    vids_stored += 1
                    comments_scraped += len(comment_data_list)
                    break
                except Exception as e:
                    if i == 2:
                        print('Last try failed, giving up')
                    stacktrace_str = traceback.format_exc()
                    print(stacktrace_str)
                    print(e)
        else:
            print('Failed to get info for {video_url}')

    if account_info:
        update_user_and_metrics(username, account_info, end_scrape_date)
    else:
        checkout_user(username, None)
    return vids_stored, comments_scraped

    

    


if __name__ == "__main__":
    main()