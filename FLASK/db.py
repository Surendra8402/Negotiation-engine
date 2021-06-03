from datetime import datetime

from bson import ObjectId
from pymongo import MongoClient, DESCENDING
from werkzeug.security import generate_password_hash

from user import User

client = MongoClient("mongodb+srv://EricTest:test@cluster0.ozw3z.mongodb.net/myFirstDatabase?retryWrites=true&w=majority")

chat_db = client.get_database("ChatDB")
users_collection = chat_db.get_collection("users")
rooms_collection = chat_db.get_collection("rooms")
room_members_collection = chat_db.get_collection("room_members")
messages_collection = chat_db.get_collection("messages")


def save_user(username, email, password):
    password_hash = generate_password_hash(password)
    users_collection.insert_one({'_id': username, 'email': email, 'password': password_hash})


def get_user(username):
    user_data = users_collection.find_one({'_id': username})
    return User(user_data['_id'], user_data['email'], user_data['password']) if user_data else None


def save_room(room_name, created_by, highest_bid,highest_bidder,closing_time):
    room_id = rooms_collection.insert_one(
        {'name': room_name, 'created_by': created_by, 'created_at': datetime.now(), 'highest_bid':highest_bid,'highest_bidder':highest_bidder,'closing_time':closing_time}).inserted_id
    add_room_member(room_id, room_name, created_by, created_by, is_room_admin=True)
    return room_id


def update_room(room_id, room_name):
    rooms_collection.update_one({'_id': ObjectId(room_id)}, {'$set': {'name': room_name}})
    room_members_collection.update_many({'_id.room_id': ObjectId(room_id)}, {'$set': {'room_name': room_name}})


def get_room(room_id):
    return rooms_collection.find_one({'_id': ObjectId(room_id)})


def add_room_member(room_id, room_name, username, added_by, is_room_admin=False):
    room_members_collection.insert_one(
        {'_id': {'room_id': ObjectId(room_id), 'username': username}, 'room_name': room_name, 'added_by': added_by,
         'added_at': datetime.now(), 'is_room_admin': is_room_admin})


def add_room_members(room_id, room_name, usernames, added_by):
    room_members_collection.insert_many(
        [{'_id': {'room_id': ObjectId(room_id), 'username': username}, 'room_name': room_name, 'added_by': added_by,
          'added_at': datetime.now(), 'is_room_admin': False} for username in usernames])


def remove_room_members(room_id, usernames):
    room_members_collection.delete_many(
        {'_id': {'$in': [{'room_id': ObjectId(room_id), 'username': username} for username in usernames]}})


def get_room_members(room_id):
    return list(room_members_collection.find({'_id.room_id': ObjectId(room_id)}))


def get_rooms_for_user(username):
    return list(room_members_collection.find({'_id.username': username}))


def is_room_member(room_id, username):
    return room_members_collection.count_documents({'_id': {'room_id': ObjectId(room_id), 'username': username}})


def is_room_admin(room_id, username):
    return room_members_collection.count_documents(
        {'_id': {'room_id': ObjectId(room_id), 'username': username}, 'is_room_admin': True})


def save_message(room_id, text, sender):
    messages_collection.insert_one({'room_id': room_id, 'text': text, 'sender': sender, 'created_at': datetime.now()})

def get_hb(room_id):   #Custom function that gets the highest bid value for a particular auction entry
    hb=rooms_collection.find_one({'_id': ObjectId(room_id)})
    valor=hb['highest_bid']
    return valor


def get_hbidder(room_id):   #Custom function that gets the highest bid value for a particular auction entry
    hb=rooms_collection.find_one({'_id': ObjectId(room_id)})
    valor=hb['highest_bidder']
    return valor

def get_closing(room_id):   #Custom function that gets the highest bid value for a particular auction entry
    hb=rooms_collection.find_one({'_id': ObjectId(room_id)})
    valor=hb['closing_time']
    valort=datetime.strptime(valor, '%Y-%m-%dT%H:%M')

    return valort

def update_bid(room_id,highest_bid,highest_bidder):
    rooms_collection.update_one({'_id': ObjectId(room_id)}, {'$set': {'highest_bid': highest_bid}})
    rooms_collection.update_one({'_id': ObjectId(room_id)}, {'$set': {'highest_bidder': highest_bidder}})


def get_messages(room_id, page=0):
   
    messages = list(
        messages_collection.find({'room_id': room_id}))
    for message in messages:
        message['created_at'] = message['created_at'].strftime("%d %b, %H:%M")
    return messages

