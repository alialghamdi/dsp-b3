from flask import Flask, render_template, session, request, redirect, jsonify, url_for
from flask_sqlalchemy import SQLAlchemy
import openai
import json
import requests
from helpers import login_required

app = Flask(__name__)

db = SQLAlchemy()

# configure the SQLite database, relative to the app instance folder
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://dsp_db_user:VIcz0CMSa8JXLQdrjkqK0y9Brvn0tFtW@dpg-cmk4b27109ks73fuiqj0-a.frankfurt-postgres.render.com/dsp_db"

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

app.config['SECRET_KEY']= ('asdasdasdaswwasdcx123akmlkds')
RIJKS_API_KEY = "kfezj3LS"
client = openai.OpenAI(api_key = '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')

# initialize the app with the extension
db.init_app(app)

# Database tables
class Art_data(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    object_number = db.Column(db.String(80))
    artist_name = db.Column(db.String(1000))
    question = db.Column(db.String(3000))
    answer_1 = db.Column(db.String(3000))
    answer_2 = db.Column(db.String(3000))
    answer_3 = db.Column(db.String(3000))
    answer_4 = db.Column(db.String(3000))
    correct_answer = db.Column(db.String(3000))

class Users(db.Model):
    user_id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100))
    score = db.Column(db.Integer, default=0)

with app.app_context():
    db.create_all()

@app.route('/login', methods=["GET", "POST"])
def login_page():
    session.clear()
    if request.method == "POST":
        email = request.form.get('email')
        exists = db.session.query(Users).filter_by(email=email).first()
        session["email"] = email
        session["count"] = 0
        if exists != None:
            return redirect('/')
        else:
            new_user = Users(email=email)
            db.session.add(new_user)
            db.session.commit()
        return redirect('/')

    return render_template('login.html')

@app.route('/')
@login_required
def index():
    return render_template("index.html")

@app.route('/quiz/<artist>')
@login_required
def quiz(artist):
    data_collection = collection_data(artist, session["count"])
    data_collection_details = collection_details_data(data_collection['id'])
    chat_gpt_data = question_and_answer_fc(data_collection_details["artObject"]['label']["description"])
    question_1 = Art_data(object_number= data_collection['id'],
                          artist_name= data_collection["longtitle"],
                          question=chat_gpt_data["question_1"],
                          answer_1=chat_gpt_data['question_1_answer_1'],
                          answer_2=chat_gpt_data['question_1_answer_2'],
                          answer_3=chat_gpt_data['question_1_answer_3'],
                          answer_4=chat_gpt_data['question_1_answer_4'],
                          correct_answer=chat_gpt_data['question_1_correct_answer'])

    question_2 = Art_data(object_number= data_collection['id'],
                          artist_name= data_collection["longtitle"],
                          question=chat_gpt_data["question_2"],
                          answer_1=chat_gpt_data['question_2_answer_1'],
                          answer_2=chat_gpt_data['question_2_answer_2'],
                          answer_3=chat_gpt_data['question_2_answer_3'],
                          answer_4=chat_gpt_data['question_2_answer_4'],
                          correct_answer=chat_gpt_data['question_2_correct_answer'])
    db.session.add(question_1)
    db.session.add(question_2)
    db.session.commit()
    return render_template("quiz.html", collection_data=data_collection, collection_details_data=data_collection_details, chat_gpt_data=chat_gpt_data, page_count=session["count"])

@app.route('/scoreboard', methods=['GET'])
@login_required
def scoreboard():
    session["count"] = 0
    top_scores = Users.query.order_by(Users.score.desc()).limit(5).all()
    return render_template("scoreboard.html", top_scores=top_scores)

@app.route('/empty_users', methods=['GET', 'POST'])
@login_required
def empty_users():
    try:
        # Delete all records from the Users table
        Users.query.delete()
        # Commit the changes to the database
        db.session.commit()
        return 'All users deleted successfully.'
    except Exception as e:
        # Handle exceptions, log errors, or provide an error message
        return f'Error deleting users: {str(e)}'

@app.route('/process_score', methods=['POST'])
def process_score():
    score = request.get_json()
    # Do something with the data, for example, print it
    score = int(score['key'])
    session["count"] = session["count"] + 1
    user = db.session.query(Users).filter_by(email=session["email"]).first()
    user.score = user.score + score
    db.session.commit()
    # Return a response back to the client
    return jsonify({"message": user.score})

if __name__ == '__main__':
    app.run(debug=True)

# Functions
def collection_data(artist, painting_count = 0):
    url = 'https://www.rijksmuseum.nl/api/en/collection?key={}&involvedMaker={}&imgonly=True&toppieces=True'.format(RIJKS_API_KEY, artist)
    response = requests.get(url)
    if response.status_code == 200:
        artwork_data = response.json()
        id = artwork_data['artObjects'][painting_count]['objectNumber']
        artist = artwork_data['artObjects'][painting_count]['principalOrFirstMaker']
        title = artwork_data['artObjects'][painting_count]['title']
        longtitle = artwork_data['artObjects'][painting_count]['longTitle']
        img_url = artwork_data['artObjects'][painting_count]['webImage']['url']

        return {'id': id, 'title': title, 'artist': artist, 'img_url': img_url, 'longtitle': longtitle}
    else:
        return f"Error: {response.status_code}"

def collection_details_data(id):
    url = 'https://www.rijksmuseum.nl/api/en/collection/{}?key={}'.format(id, RIJKS_API_KEY)
    response = requests.get(url)
    if response.status_code == 200:
        artwork_data = response.json()
        return artwork_data
    else:
        return f"Error: {response.status_code}"

def to_json(response):
    response_body = response.choices[0].message.content
    json_start_marker = "```json"
    json_end_marker = "```"

    start_index = response_body.find(json_start_marker)
    end_index = response_body.find(json_end_marker, start_index + len(json_start_marker))

    if start_index != -1 and end_index != -1:
        json_content = response_body[start_index + len(json_start_marker):end_index]
        return json_content
    else:
        return False

functions =   [
        {
            "name": "show_art_info",
            "description": "Shows information about the artwork",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "the title of the painting"
                    },
                    "subject": {
                        "type": "string",
                        "description": "the subject of the painting"
                    },
                    "paiting_style": {
                        "type": "string",
                        "description": "the style of the painting"
                    },
                    "description": {
                        "type": "string",
                        "description": "a description of the painting"
                    },
                    "not_typical": {
                        "type": "string",
                        "description": "explaining how the painting doesn't relate to Painter X's typical style or themes"
                    },
                    "question_1": {
                        "type": "string",
                        "description": "the first multipechoice question about the painting"
                    },
                    "question_2": {
                        "type": "string",
                        "description": "the second multipechoice question about the painting"
                    },
                    "question_1_answer_1": {
                        "type": "string",
                        "description": "the first possible answer to the first multipechoice question"
                    },
                    "question_1_answer_2": {
                        "type": "string",
                        "description": "the second possible answer to the the first multipechoice question"
                    },
                    "question_1_answer_3": {
                        "type": "string",
                        "description": "the third possible answer to the the first multipechoice question"
                    },
                    "question_1_answer_4": {
                        "type": "string",
                        "description": "the forth possible answer to the the first multipechoice question"
                    },
                    "question_1_correct_answer": {
                        "type": "string",
                        "description": "the correct answer to the first multipechoice question"
                    },
                    "question_2_answer_1": {
                        "type": "string",
                        "description": "the first possible answer to the second multipechoice question"
                    },
                    "question_2_answer_2": {
                        "type": "string",
                        "description": "the second possible answer to the the second multipechoice question"
                    },
                    "question_2_answer_3": {
                        "type": "string",
                        "description": "the third possible answer to the the second multipechoice question"
                    },
                    "question_2_answer_4": {
                        "type": "string",
                        "description": "the forth possible answer to the the second multipechoice question"
                    },
                    "question_2_correct_answer": {
                        "type": "string",
                        "description": "the correct answer to the second multipechoice question"
                    },
                }
            }
        }
    ]
def question_and_answer_fc(description):
    response = client.chat.completions.create(
        model="gpt-4-1106-preview",
        messages=[
            {
                "role": "system",
                "content": "You are passionate about art and working on making multiple choice questions to help general population to learn about art. Your focus is now on the Rijksmuseum in Amsterdam. Return in JSON"
            },
            {
                "role": "user",
                "content": [
                    {"type": "text",
                     "text": "For this painting, give two multiple choice questions with 4 possible answers and label the right answer? One question should be based on a visual element that can be seen. The second question should be based on the description of the painting which is provided below by me."},
                    {"type": "text", "text": description},
                ],
            }
        ],
        max_tokens=1200,
        functions=functions,
        function_call={
            "name": "show_art_info"
        }
    )

    arguments = (response.choices[0].message.function_call.arguments)
    json.loads(arguments)
    return json.loads(arguments)

def question_and_answer(description, url):
    response = client.chat.completions.create(
        model="gpt-4-vision-preview",
        messages=[
            {
                "role": "system",
                "content": "You are passionate about art and working on making multiple choice questions to help general population to learn about art. Your focus is now on the Rijksmuseum in Amsterdam. Return in JSON"
            },
            {
                "role": "user",
                "content": [
                    {"type": "text",
                     "text": "For this painting, give two multiple choice questions with 4 possible answers and label the right answer? One question should be based on a visual element that can be seen. The second question should be based on the description of the painting which is provided below by me."},
                    {"type": "text", "text": description},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": url,
                        },
                    },
                ],
            }
        ],
        max_tokens=1200,
    )
    return json.loads(to_json(response))