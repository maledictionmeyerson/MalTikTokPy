import config
from datetime import datetime
import os
from sqlalchemy.exc import SQLAlchemyError
from db import create_session, setup_database


def file_to_list_of_strings(filename):
    with open(filename, 'r') as file:
        list_of_strings = [line.rstrip('\n') for line in file]
    return list_of_strings

def add_accounts(fileName, source):
    account_list = file_to_list_of_strings(fileName)
    config.SESS = create_session()
    config.BASE = setup_database(config.SESS)
    TTUsers = config.BASE.classes.ttusers

    # Fetch existing usernames from the database that match the account_list
    existing_accounts = config.SESS.query(TTUsers.username).filter(TTUsers.username.in_(account_list)).all()
    existing_accounts_set = set([item[0] for item in existing_accounts])
    

    # Filter out existing accounts from the account_list
    accounts_to_insert = set()
    for account in account_list:
        if account not in existing_accounts_set:
            accounts_to_insert.add(account)
    current_time = datetime.now()
    print(len(account_list))
    print(len(accounts_to_insert))
    input()

    new_accounts = [
        {
            'username': account,
            'account_discovered_by': source,
            'date_inserted': current_time
        }
        for account in accounts_to_insert
    ]

    # Use the bulk_insert_mappings method for more efficient bulk inserts
    config.SESS.bulk_insert_mappings(TTUsers, new_accounts)
    
    # Commit the changes
    config.SESS.commit()

    query = config.SESS.query(TTUsers)
    print(f"New total # of accounts {query.count()}")

def add_account(account_name, source):
  
    # config.SESS = create_session()
    # config.BASE = setup_database(config.SESS)
    TTUsers = config.BASE.classes.users_cross_platform

    # Fetch existing usernames from the database that match the account_list
    existing_accounts = config.SESS.query(TTUsers.username).filter(TTUsers.username.in_([account_name])).all()
    if account_name in existing_accounts:
        print('Already have account, continuing')
        return
    existing_accounts_set = set([item[0] for item in existing_accounts])
    

    # Filter out existing accounts from the account_list
    accounts_to_insert = set()
    accounts_to_insert.add(account_name)
    
    current_time = datetime.now()

    new_accounts = [
        {
            'username': account,
            'account_discovered_by': source,
            'date_inserted': current_time,
            'platform': 'TikTok'
        }
        for account in accounts_to_insert
    ]

    # Use the bulk_insert_mappings method for more efficient bulk inserts
    config.SESS.bulk_insert_mappings(TTUsers, new_accounts)
    
    # Commit the changes
    config.SESS.commit()

    query = config.SESS.query(TTUsers)
    print(f"New total # of accounts {query.count()}")


def add_post(video_info, video_metrics):

    post_url = video_info['post_url']

    Posts = config.BASE.classes.posts_cross_platform
    PostMetrics = config.BASE.classes.post_metrics_cross_platform

    existing_post = config.SESS.query(Posts.post_url).filter(Posts.post_url == post_url)
    existing_post_metrics = config.SESS.query(PostMetrics.post_url).filter(PostMetrics.post_url == post_url)

    post_count = existing_post.count()
    metric_count = existing_post_metrics.count()
    if not post_count:
        caption = None
        if video_info['caption']:
            caption = video_info['caption'][:2200]
        new_post = Posts(
            post_url=post_url,
            username=video_info['username'],
            date_posted=video_info['date_posted'],
            img_urls=video_info['img_urls'],
            caption=caption,
            hashtags=video_info['hashtags'],
            platform='TikTok'
        )
        config.SESS.add(new_post)
        config.SESS.commit()
        print(f"Added new post: {post_url}")
    
    if not metric_count:
        new_post_metrics = PostMetrics(
            post_url=post_url,
            date_posted=video_metrics['date_posted'],
            date_collected=video_metrics['date_collected'],
            num_likes=video_metrics['num_likes'],
            num_comments=video_metrics['num_comments'],
            num_views=video_metrics['num_views'],
        )
        config.SESS.add(new_post_metrics)
        config.SESS.commit()
        print(f"Added new post metrics: {post_url}")
    else:
        print(f'Post: {post_url} already exists')

def add_comments(comment_data_list):
    Comments = config.BASE.classes.post_comments_cross_platform

    id_list = [comment_data['id'] for comment_data in comment_data_list]
    post_url = comment_data_list[0]['post_url']

    # Query existing comments to avoid duplicates
    existing_post_comments = config.SESS.query(Comments.id).filter(Comments.id.in_(id_list)).filter(Comments.post_url == post_url).all()
    existing_post_comments_set = set([item[0] for item in existing_post_comments])

    # Filter out existing comments
    comments_to_insert = [comment for comment in comment_data_list if comment['id'] not in existing_post_comments_set]

    # Remove duplicates within the new comments based on 'id'
    ids = set()
    new = []
    for comment in comments_to_insert:
        if comment['id'] not in ids:
            new.append(comment)
            ids.add(comment['id'])
    comments_to_insert = new

    # Prepare the comments for insertion
    new_comments = [
        {
            'comment_text': comment['comment_text'],
            'post_url': comment['post_url'],
            'num_likes': comment['num_likes'],
            'commenter_username': comment['commenter_username'],
            'date_collected': comment['date_collected'],
            'id': comment['id'],
            'channel': 'byAccount'
        } for comment in comments_to_insert
    ]

    # Attempt bulk insert
    try:
        config.SESS.bulk_insert_mappings(Comments, new_comments)
        config.SESS.commit()
    except SQLAlchemyError as e:
        print(f"Bulk insert failed: {e}")
        config.SESS.rollback()
        # Attempt insert in batches of 50
        for i in range(0, len(new_comments), 50):
            batch = new_comments[i:i+50]
            try:
                config.SESS.bulk_insert_mappings(Comments, batch)
                config.SESS.commit()
            except SQLAlchemyError as e:
                print(f"Batch insert failed: {e}")
                config.SESS.rollback()
                # Insert comments individually within the failed batch
                for comment_data in batch:
                    try:
                        new_comment = Comments(**comment_data)
                        config.SESS.add(new_comment)
                        config.SESS.commit()
                    except SQLAlchemyError as e:
                        print(f"Error inserting comment {comment_data['id']}: {e}")
                        config.SESS.rollback()

    # Final query to count total comments for the post
    query = config.SESS.query(Comments).filter(Comments.post_url == post_url)
    print(f"New total # of comments for post {query.count()}")

def checkout_user(username, scrape_end):
    Users = config.BASE.classes.users_cross_platform
    config.SESS.query(Users).filter(Users.username == username).update({
        Users.pulling_data_last_started: scrape_end,
    })
    config.SESS.commit()



def update_user_and_metrics(username, metrics, scrape_end, accountDeleted=False, accountPrivate=False):
    return
    Users = config.BASE.classes.users_cross_platform
    # UserMetrics = config.BASE.classes.user_metrics_cross_platform
    
    current_time = datetime.utcnow()
    
    # If account is deleted, update does_not_exist column
    if accountDeleted:
        config.SESS.query(Users).filter(Users.username == username).update({Users.does_not_exist: True})
        config.SESS.commit()
        return
    if accountPrivate:
        config.SESS.query(Users).filter(Users.username == username).update({Users.is_private: True})
        config.SESS.commit()
        return
    
    # Update the pulling_data_last_started and date_metrics_last_collected in ttusers table
    config.SESS.query(Users).filter(Users.username == username).update({
        Users.date_metrics_last_collected: current_time
    })
    
    # Insert/Update metrics into ttuser_metrics table
    existing_metric = config.SESS.query(UserMetrics).filter_by(username=username, date_collected=current_time).first()

    if existing_metric:
        # Update the existing record
        existing_metric.num_followers = metrics['num_followers']
        existing_metric.num_following = metrics['num_following']
        existing_metric.num_posts = metrics['num_posts']
        existing_metric.is_verified = metrics['verified']
    else:
        # Insert a new record
        new_metrics = UserMetrics(
            username=username,
            num_followers=metrics['num_followers'],
            num_following=metrics['num_following'],
            num_posts=metrics['num_posts'],
            is_verified=metrics['verified'],
            date_collected=current_time
        )
        config.SESS.add(new_metrics)

    config.SESS.commit()
    

def add_post_attempt(num_comments_scraped, attempt_num, post_url):
    TTPostAttempts = config.BASE.classes.ttpost_attempts
    new_attempt = TTPostAttempts(
        post_url=post_url,
        num_comments=num_comments_scraped,
        try_number=attempt_num
    )
    config.SESS.add(new_attempt)
    config.SESS.commit()
    print(f"Added new post attempt: {num_comments_scraped} comments scraped, attempt {attempt_num}")