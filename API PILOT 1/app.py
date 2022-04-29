from datetime import datetime

from bson.json_util import dumps
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_cors import CORS
from pymongo.errors import DuplicateKeyError
import json
import dateutil.parser
import logging

from db import (
    neg_info, save_param2,sign_contract,change_status, get_neg,owned_auctions,get_bidders,find_rooms,distance_calc,
    ended,get_room_admin,save_param,add_room_member,add_room_members, save_room2,update_bid,
    get_closing,get_hb,get_sign,get_hbidder, get_messages, get_room, get_room_members, get_user, is_room_admin,
    is_room_member, remove_room_members, save_bid, save_room, save_user, update_room, get_room_details, get_room_details_by_ids,
    get_all_rooms_by_id, get_rooms_by_username, get_negotiations_by_username, create_contract, get_contract, list_contracts,
    get_negotiation, get_public_rooms, sign_negotiation_contract, get_user_loc,add_loc,represented_cont,
    detect_broker,broker_contracts,new_broker
)
from db import JSONEncoder

app = Flask(__name__)

from transport.broker_transport import *

cors = CORS(app)
app.secret_key = "sfdjkafnk"
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

logging.basicConfig(level=logging.DEBUG)

def int_or_default(s, default):
    try:
        return int(s)
    except:
        return default


# The login route receives the username and password as a POST request

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return {"message":"The user {} is already authenticated".format(current_user)},200

    message = ''
    if request.method == 'POST':
        username = request.form.get('username')
        password_input = request.form.get('password')
        user = get_user(username)

        if user and user.check_password(password_input):
            login_user(user)
           
            return {"message":"User {} has been authenticated".format(str(user.username))},200
        else:
            message = 'Failed to login!'
    return message,400


# Signup function is not habilitated for the time being, users are to be created either
# by function or directly into the database

@app.route('/signup', methods=['POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    username = request.json.get('username')
    email = request.json.get('email')
    password = request.json.get('password')
    sign=request.json.get('sign')
    location=request.json.get('sign')
    try:
        save_user(username, email, password, sign, location)
        return { 'message': "User created" }, 200
    except DuplicateKeyError:
        return { 'message': "User already exists!" }, 400

##holi={"room_name":"Erics composite auction","members":"","highest_bid":"5000","auction_type":"Ascending","closing_time":"2021-07-06T10:34:20","reference_sector":"Composites","reference_type":"Electronic","quantity":"15","templatetype":"article","articleno":"23dd"}


# A request to this function will log out the user from the server

@app.route("/logout/")
@login_required
def logout():
    logout_user()
    return {'message':'the user has logged out'},200


# Use a POST request to create a new auction, user has to be logged in

@app.route('/create-room', methods=['GET', 'POST'])
#@login_required
def create_room():
    if request.method == 'POST':
        privacy= request.form.get('privacy')
        room_name = request.form.get('room_name')
        highest_bid=request.form.get('highest_bid')
        highest_bidder=''
        auction_type=request.form.get('auction_type')
        closing_time=dateutil.parser.isoparse(request.form.get('closing_time'))
        reference_sector=request.form.get('reference_sector')
        reference_type=request.form.get('reference_type')
        quantity=request.form.get('quantity')
        articleno=request.form.get('articleno')
        user=request.authorization.username
        sellersign=get_sign(user)
        buyersign=''
        templatetype=request.form.get('templatetype')
        location=request.form.get('auction_location')
        is_broker=request.form.get('is_broker')
        broker_id=request.form.get('broker_id')
        if is_broker:
            broker_contract=represented_cont(broker_id)
            represented_by=user
            user=broker_contract['represented']
        else: 
            broker_id,represented_by='',''
        if(request.form.get('members')):
            usernames = [username.strip() for username in request.form.get('members').split(',')]
        else: 
            usernames=[user]

        if len(room_name) and len(usernames):
                      
            room_id = save_room(privacy, room_name, user,auction_type,highest_bid,highest_bidder,closing_time,sellersign,buyersign,templatetype,location,is_broker,broker_id,represented_by)
            save_param(room_id,user,room_name,reference_sector,reference_type,quantity,articleno)
            if user in usernames:
                usernames.remove(user)
            if len(usernames)>=1:
                add_room_members(room_id, room_name, usernames, user)
            return {"message":"The room {} has been created id: {}".format(str(room_name),room_id)},200
        else:
            return {"message":"Unable to create room"},400  #Reformat to make it clearer


# Edit room also is not enabled but should work with little effort if needed

@app.route('/rooms/<room_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_room(room_id):
    room = get_room(room_id)
    if room and is_room_admin(room_id, current_user.username):
        existing_room_members = [member['_id']['username'] for member in get_room_members(room_id)]
        room_members_str = ",".join(existing_room_members)
        message = ''
        if request.method == 'POST':
            room_name = request.json.get('room_name')
            room['name'] = room_name
            update_room(room_id, room_name)

            new_members = [username.strip() for username in request.json.get('members').split(',')]
            members_to_add = list(set(new_members) - set(existing_room_members))
            members_to_remove = list(set(existing_room_members) - set(new_members))
            if len(members_to_add):
                add_room_members(room_id, room_name, members_to_add, current_user.username)
            if len(members_to_remove):
                remove_room_members(room_id, members_to_remove)
            message = 'Room edited successfully'
            room_members_str = ",".join(new_members)
        return render_template('edit_room.html', room=room, room_members_str=room_members_str, message=message)
    else:
        return "Room not found", 404



# GET request to this route has to include room_id for the room you want to join but no aditional parameters are needed

@app.route('/rooms/<room_id>/join', methods=['GET'])
#@login_required
def join_room(room_id):
    """
    This function is used when user is joining a particular auction.
    The same function is used when a user already in an auction submits a request WITHOUT the location field

    In the case a user is broker, it gets requested what is the broker_id which can be get with the broker view
    """
    room = get_room(room_id)
    room_name=room['payload']['name']['val'][0]
    user=request.authorization.username
    location=request.json.get("location")
    is_broker=request.json.get("is_broker")  ##Ideally a checkbox in frontend
    broker_id=request.json.get("broker_id")  ##Only required if the checkbox is on


    existing_room_members = [member['_id']['username'] for member in get_room_members(room_id)]
    if request.method == 'GET':
        new_members = user
        if is_broker==True:
            ## Get name of representant and change user to that one
            broker_contract=represented_cont(broker_id)
            represented_by=user
            user=broker_contract['represented']
            if new_members in list(set(existing_room_members)):
                if get_user_loc(user,room_id)=='':
                    if location:
                        add_loc(user,room_id,location,is_broker,broker_id)
                        return{"message":"Added location for user"},200
                    else:  return {"message":"User has no location"},404
                return {"message":"You are already in a room"},200
            add_room_member(room_id, room_name, new_members, user, location,is_broker,broker_id,represented_by)
        else:
            if new_members in list(set(existing_room_members)):
                if get_user_loc(user,room_id)=='':
                    if location:
                        add_loc(user,room_id,location,False,'')
                        return{"message":"Added location for user"},200
                    else:  return {"message":"User has no location"},404
                return {"message":"You are already in a room"},200
            add_room_member(room_id, room_name, new_members, user, location,False,'','')
        
    return {"message":"You have joined the room {}".format(str(room_name))},200




# A POST request to this route will receive parameter message_input and will generate a bid to the auction
# A GET request will show all the messages submited to this auction.

@app.route('/rooms/<room_id>', methods=['GET','POST'])
#@login_required
def bid(room_id):
    room = get_room(room_id)
    rn=room['payload']['name']['val'][0]
    closing_time=get_closing(room_id)
    broker_represented=detect_broker(room_id,user) #Returns name of represented user if true, false otherwise

    user=broker_represented if broker_represented else request.authorization.username

    if room and is_room_member(room_id, user):
        
        ## The event for the timeout message could go here
        
        if request.method=='POST':
            bid=request.form.get("bid")
            bidder_loc=get_user_loc(user,room_id)
            if (closing_time)>datetime.utcnow():
                if(is_room_admin(room_id,user)==0):
                    if bidder_loc=='': ##If user has no location in the auction, error will rise 
                        return{"message":"User has no location associated with this room"},404     
                    sign=get_sign(user)
                    ## Calculation of distance between users done at every bid
                    distance=distance_calc(bidder_loc,room['payload']['location']['val'][0])
                    #
                    save_bid('auction',str(room['_id']),bid,user,sign,distance)  
                    app.logger.info("{} has summited a new bid to the room {}: {}".format(user,
                                                                            rn,
                                                                            bid))                  
                else:
                    app.logger.info("Cannot bid if you are Admin")  
                    return{"message":"You cannot issue bids as room admin"},400                          
            else:
                app.logger.info("Auction time has ended")
                return {"message":"The auction {} has already ended".format(str(rn))},400
            return {"message":"You have issued the bid {}".format(str(bid))},200
        elif request.method=='GET':
            messages = get_messages(room_id)
            if room and is_room_member(room_id, user):
                
                ## Here the bids from all users are shown to the user 
                
                keys = ['sender','text', 'created_at','distance']
                d=[]
                for message in messages:
                    m_pay=message['payload']
                    filtered_d = dict((k, m_pay[k]) for k in keys if k in m_pay)
                    d.append(filtered_d)

                body = {"Bids": d}
                
                return JSONEncoder().encode(body), 200

    else:
        return "Room not found or user is not member", 404


# A POST request to this auction is used to select the winner with the paremeter "winner" only in case no winner is selected yet
# A GET request in case the auction isnt ended will display the highest bids from all the biders
# and will show the ricardian contract in case the auction is ended

@app.route('/rooms/<room_id>/end', methods=['GET','POST'])
##@login_required
def winner(room_id):
    
    closing_time=get_closing(room_id)
    
    room = get_room(room_id)
    
    rn=room['payload']['name']['val'][0]
    contract_title = room['payload']['templatetype']['val'][0]
    
    user=request.authorization.username

    broker_represented=detect_broker(room_id,user) #Returns name of represented user if true, false otherwise

    user=broker_represented if broker_represented else request.authorization.username
## Withing this function the logic for the winner selection is specified, the admin shall input the username of the winner
    if request.method=='POST':
        
        if(is_room_admin(room_id,user)==1):
            
            if (closing_time)>datetime.utcnow(): #Auction hasnt ended
                    return{"message":"The specified auction hasnt ended"},400
            if get_hbidder(room_id)=='': ## This would mean the auction doesnt have a winner yet
                winner=request.form.get("winner") #Should be username
                wi=json.loads(get_hb(room_id,winner)) ## Get hb should be changed in case the auction is descending
                if wi:
                    for d in wi:
                        sen=d['sender']
                        bid=d['text']
                        sign=d['sign']
                    update_bid(room['_id'],bid,sen,sign)
                    return {"message":"winner has been selected"},200
                else: 
                    return {"message":"User does not participate the auction"},403
            else: 
                return {"message":"the winner for this auciton has already been selected"},200
        else: return{"message":"You are not room admin"},400
    elif request.method=='GET':
        if user == get_room_admin(rn):
            if get_hbidder(room_id)=='': #Winner hasnt been selected
                return get_bidders(room_id),200
            else: #Winner is selected
                response={'contract':ended(room_id, contract_title)}
                return jsonify(response),200
        elif (user==get_hbidder(room_id)):
            response={'contract':ended(room_id, contract_title)}
            return jsonify(response),200
        elif get_hbidder(room_id)=='':
            return {"message":"Winner hasnt been selected"},400
        else: 
            return {"message":"The auction has ended, the winner is {}".format(room['highest_bidder'])},400


            
# A GET request to this route is used to query auction based in the parameters listed below

@app.route('/rooms', methods=['GET'])
#@login_required
def query():
    
    if request.method=='GET':
        user=request.authorization.username
        room_type=request.json.get("room_type")
        room_name=request.json.get("room_name")
        reference_sector=request.json.get("reference_sector")
        reference_type=request.json.get("reference_type")
        ongoing=request.json.get("ongoing")
        distance= request.json.get("distance")
        location=request.json.get("location") ##Needed
        is_broker=request.json.get('is_broker')
        broker_id=request.json.get('broker_id')
        if is_broker:
            broker_contract=represented_cont(broker_id)
            user=broker_contract['represented']
        auctions=find_rooms(room_name,reference_sector,reference_type,ongoing,user,distance,location)
        return auctions,200


@app.route('/myrooms/admin',methods=['GET'])
def myauct_a():
    if request.method=='GET':
        user=request.authorization.username
        is_broker=request.json.get('is_broker')
        broker_id=request.json.get('broker_id')
        if is_broker:
            broker_contract=represented_cont(broker_id)
            user=broker_contract['represented']
        owner=True
        auct=owned_auctions(user,owner)
        return auct,200 


@app.route('/myrooms/user',methods=['GET'])
def myauct_u():
    if request.method=='GET':
        user=request.authorization.username
        is_broker=request.json.get('is_broker')
        broker_id=request.json.get('broker_id')
        if is_broker:
            broker_contract=represented_cont(broker_id)
            user=broker_contract['represented']
        owner=False
        auct=owned_auctions(user,owner)
        return auct,200 


# Start negotiation: 
# To be done: Verify validity of inputs, for example, x permision for y database is possible

@app.route("/negotiate", methods=['POST'])
def new_neg():

    room_name = request.form.get('room_name')
    bid=request.form.get('price')
    bidder=request.authorization.username
    seller=request.form.get('seller')
    seller_loc=request.form.get('seller_loc_id') #this parameter should be fed with the location embeded to the offers, shall this be in the url let me know
    reference_sector=request.form.get('reference_sector')
    reference_type=request.form.get('reference_type')
    quantity=request.form.get('quantity')
    articleno=request.form.get('articleno')
    user_location=request.form.get('bid_loc_id')
    buyersign=get_sign(bidder)
    sellersign=''
    templatetype=request.form.get('templatetype')
    distance=distance_calc(user_location,seller_loc)
    is_broker=request.form.get('is_broker')
    broker_id=request.form.get('broker_id')
    if is_broker:
        broker_contract=represented_cont(broker_id)
        bidder=broker_contract['represented']
    
    #The following function may be changed to iterate if multiple roles are requested
    room_id=save_room2(room_name,bidder,seller,seller_loc,sellersign,buyersign,templatetype,bid,distance)
    save_param2(room_id,bidder,room_name,reference_sector,reference_type,quantity,articleno)
    return {"message":"The negotiation with id {} has been created".format(str(room_id))},200



# This is once the negotiation has been created 
@app.route("/negotiate/<neg_id>", methods=['GET','POST'])
def neg(neg_id):
    user = request.authorization.username
    broker_represented=detect_broker(neg_id,user) #Returns name of represented user if true, false otherwise

    user=broker_represented if broker_represented else request.authorization.username
    req = get_neg(neg_id)
    name = req['payload']['name']['val'][0]

    if request.method == 'POST':
        bid = request.form.get('bid')
        creator = req['payload']['created_by']['val'][0]
        participant = req['payload']['seller']['val'][0]
        #neg_loc=req['payload']['location']['val'][0]
        status = req['payload']['status']['val'][0]

        if user in (creator, participant):
            if status not in ('accepted', 'rejected'):
                #distance = distance_calc(bidder_loc, neg_loc) No point in adding distance in every bid as is a p2p
                save_bid('negotiation',neg_id, bid, user, get_sign(user), 'na')
                change_status(neg_id, 1, user, bid)

                return { "message": "New offer submited for request with id {}".format(str(req['_id'])) }, 200
            else:
                return { "message": "The negotiation {} has concluded no more offers can be made".format(str(req['_id'])) }, 403
        else:
            return { "message": 'You are not part of the current negotiation' }, 403
    
    elif (request.method=='GET'):
        status = req['payload']['status']['val'][0]
        if user in (creator, participant):
            if status == 'accepted':
                s = sign_contract(neg_id)
                return  {"Contract": "{}".format(s)}, 200
            else:
                return(neg_info(neg_id)), 200
        else: return{'message':'Cannot access negotiation as user is not part of it'},403


# Only accesible to the owner of such resource, this route accepts the negotiation and begins the contract signing
@app.route("/negotiate/<req_id>/accept", methods=['GET'])
def accept(req_id):
    user=request.authorization.username
    req=get_neg(req_id)
    broker_represented=detect_broker(req_id,user) #Returns name of represented user if true, false otherwise
    user=broker_represented if broker_represented else request.authorization.username
    if user != req['payload']['offer_user']['val'][0]:
        if (user == req['payload']['created_by']['val'][0]) or ((user == req['payload']['seller']['val'][0])):
            flag=change_status(req_id, 'accept',user,0)
            
            ## Add function for contract writing
            if flag: 
                return  {"message":"The negotiation with id {} has been accepted.".format(str(req['_id']))},200
            else:
                return  {"message":"Could not process request, either the accepted auction is already finished or it was declined.".format(str(req['_id']))},200
        else:
            return {"message":'You are not authorized to perform this task'},403
    else:
        return {"message":'Wait for the other peer to accept or counter offer'},403


# Only accesible to the owner of such resource, this route cancels the negotiation.
@app.route("/negotiate/<req_id>/cancel", methods=['GET'])
def cancel(req_id):
    req=get_neg(req_id)
    user=request.authorization.username
    broker_represented=detect_broker(req_id,user) #Returns name of represented user if true, false otherwise

    user=broker_represented if broker_represented else request.authorization.username
    if user != req['payload']['offer_user']['val'][0]:
        if (user == req['payload']['created_by']['val'][0]) or ((user == req['payload']['seller']['val'][0])):
            flag=change_status(req_id, 'reject',user,0)

            ## Add function for contract writing
            if flag: 
                return  {"message":"The negotiation with id {} has been rejected.".format(str(req['_id']))},200
            else:
                return  {"message":"Could not process request, either the accepted auction is already finished or it was declined.".format(str(req['_id']))},200
        else:
            return {"message":'You are not authorized to perform this task'},403
    else:
        return {"message":'You are not allowed to cancel this transaction'},403


@app.route("/negotiate/<neg_id>/full", methods=["GET"])
def get_negotiation_full(neg_id):
    """
    Gets the full information of a negotiation. This includes the negotiation and
    its details.
    """
    username = request.authorization.username
    broker_represented=detect_broker(neg_id,username) #Returns name of represented user if true, false otherwise

    username=broker_represented if broker_represented else request.authorization.username
    app.logger.info("%s requesting negotiation %s", username, neg_id)

    negotiation = get_negotiation(neg_id)
    print(negotiation)
    if negotiation["status"] == "accepted":
        contract_id = negotiation["contract_template"]
        negotiation["contract"] = sign_negotiation_contract(neg_id, contract_id)
    else:
        negotiation["contract"] = ""

    return JSONEncoder().encode(negotiation), 200


@app.route("/negotiate/list", methods=["GET"])
def list_negotiations():
    """
    Gets a list of all the negotiations a user is part of.
    """
    username = request.authorization.username
    is_broker=request.form.get('is_broker')
    broker_id=request.form.get('broker_id')
    if is_broker:
        broker_contract=represented_cont(broker_id)
        username=broker_contract['represented']
    count = request.args.get('count', default=10, type=int)
    skip = request.args.get('skip', default=0, type=int)
    app.logger.info("%s requesting negotiation list, count=%s, skip=%s", username, count, skip)

    negotiations = get_negotiations_by_username(username, count, skip)
    return JSONEncoder().encode(negotiations), 200


def combine_room_with_room_details(room, room_details):
    """
    Helper to combine a room with room details. Keeps the room mostly intact,
    merging the payload only with room details
    """
    room['payload'] = { **room['payload'], **room_details['payload'] }
    return room


@app.route('/rooms/<room_id>/info', methods=['GET'])
def get_room_info(room_id):
    """
    Returns the complete information about the auction. Combines the result of the
    room, room_details, room_members, and messages (bids) collections.

    Errors:
    - If the privacy is not set to public it checks that the user is a part of the auction,
      if not a 400 Bad Request is returned.
    """
    username = request.authorization.username
    broker_represented=detect_broker(room_id,username) #Returns name of represented user if true, false otherwise

    username=broker_represented if broker_represented else request.authorization.username
    app.logger.info("%s requesting auction %s information", username, room_id)

    room = get_room(room_id)
    if room['privacy'] != 'Public' and not is_room_member(room_id, username):
        app.logger.error("%s not authorized to retrieve auction %s", username, room_id)
        return { 'message': 'Not authorized to view this auction' }, 403

    details = get_room_details(room_id)
    members = get_room_members(room_id)
    bids = get_bidders(room_id)
    
    room = combine_room_with_room_details(room, details)
    room['members'] = members
    room['bids'] = json.loads(bids)

    return JSONEncoder().encode(room), 200


def combine_room_with_room_details_and_bids(room, room_details, bids):
    """
    Helper to combine a room with room details. Keeps the room mostly intact,
    merging the payload only with room details
    """
    room['payload'] = { **room['payload'], **room_details['payload'] }
    room['bids'] = bids
    return room


@app.route('/rooms/all', methods=['GET'])
def get_all_rooms():
    """
    Returns all the rooms the user is a part of. Return room and room details with bids.
    """
    username = request.authorization.username
    is_broker=request.form.get('is_broker')
    broker_id=request.form.get('broker_id')
    if is_broker:
        broker_contract=represented_cont(broker_id)
        username=broker_contract['represented']
    app.logger.info("%s requesting all auctions the user is part of", username)

    # This isn't ideal since it gets ALL the rooms the user is a part of. Even historical,
    # but it should be fine for smaller amount of rooms.
    room_ids = get_rooms_by_username(username)
    rooms = list(get_all_rooms_by_id(room_ids))

    # Fetch additional information about rooms.
    active_room_ids = [room['_id'] for room in rooms]
    active_room_details = list(get_room_details_by_ids(active_room_ids))
    details_lookup = { str(room['_id']): room for room in active_room_details }

    bids_lookup = { str(room_id): json.loads(get_bidders(str(room_id))) for room_id in room_ids}

    # Combine room with details.
    rooms_with_details = [combine_room_with_room_details_and_bids(room, details_lookup[str(room['_id'])], bids_lookup[str(room['_id'])]) for room in rooms ]

    return JSONEncoder().encode(rooms_with_details), 200


@app.route("/rooms/public", methods=["GET"])
def route_list_public_auctions():
    """
    Returns all available public auctions
    """
    username = request.authorization.username
    is_broker=request.form.get('is_broker')
    broker_id=request.form.get('broker_id')
    if is_broker:
        broker_contract=represented_cont(broker_id)
        username=broker_contract['represented']
    skip = int_or_default(request.args.get("skip"), 0)
    limit = int_or_default(request.args.get("limit"), 20)
    app.logger.info("%s requesting all public auctions. skip: %d, limit: %d", username, skip, limit)

    (rooms, count) = get_public_rooms(skip, limit)
    ids = [room["_id"] for room in rooms]
    details = list(get_room_details_by_ids(ids))
    details_lookup = { str(room["_id"]): room for room in details }

    # Combine room with details.
    rooms_with_details = [combine_room_with_room_details(room, details_lookup[str(room["_id"])]) for room in rooms ]

    return JSONEncoder().encode({
        "rooms": rooms_with_details,
        "count": count,
    }), 200


@app.route("/contracts/create", methods=["POST"])
def route_create_contract():
    """
    Create a new contract.

    This is expected to be used by site administrators only.

    Expects:
    ```json
    {
        "title": "contract title",
        "body": "contract body, can use $identifier for templated data"
    }
    ```
    """
    body = {
        "title": request.json.get("title"),
        "body": request.json.get("body"),
    }
    for (key, value) in body.items():
        if value is None:
            return { "message": "{} must be present".format(key) }, 400
    
    app.logger.info("creating contract %s: %s", body["title"], body["body"])

    id = create_contract(**body)
    return {
        "message": "successfully created contract",
        "id": str(id),
    }, 200


@app.route("/contracts/<id>", methods=["GET"])
def route_get_contract(id):
    """
    Returns the complete information about a single contract.

    Example response:
    ```json
    {
        "_id": "",
        "title": "",
        "body": ""
    }
    ```
    """
    app.logger.info("get contract %s", id)
    contract = get_contract(id)
    if contract is None:
        return { "message": "contract not found" }, 404
    
    return JSONEncoder().encode(contract), 200


@app.route("/contracts/list", methods=["GET"])
def route_list_contracts():
    """
    Returns a list of all contracts, containing only the id and the title.

    Example response:
    ```json
    [
        {
            "_id": "",
            "title": ""
        }
    ]
    ```
    """
    app.logger.info("list all contracts")
    contracts = list_contracts()
    return JSONEncoder().encode(contracts), 200

#_____________Broker_________________


# """
# Will return broker contracts represented by the user if any,
# """
# @app.route('/broker',methods=['GET'])
# def get_broker():
#     username = request.authorization.username
#     conts=broker_contracts(username) # returns {{'represents in':{...}},{'is represented in':{...}}}
#     return conts,200 if conts is not None else {'message':'No contracts available'},404 



# @app.route('/broker/new_broker',methods=["POST"])
# def add_new_broker():
#     username = request.authorization.username
#     representant=username
#     represented=request.form.get('represented_user')
#     end_date=dateutil.parser.isoparse(request.form.get('end_date'))
#     contract_id=new_broker(representant,represented,end_date)
#     return {
#     "message": "successfully created broker agreement",
#     "id": str(contract_id),
#     }, 200


@login_manager.user_loader
def load_user(username):
    return get_user(username)


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
