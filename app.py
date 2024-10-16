# STANDARD python imports
import os
import json
import shutil
import logging
import time

# Imports for building RESTful API
from flask import Flask, request, jsonify
from flask import flash, redirect, url_for
from werkzeug.utils import secure_filename

# Imports for BRAD library
from BRAD.agent import Agent
from BRAD.rag import create_database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# HARDCODED VALUES
UPLOAD_FOLDER = '/usr/src/uploads'
DATABASE_FOLDER = '/usr/src/RAG_Database/'

SOURCE_FOLDER = '/usr/src/brad'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

TOOL_MODULES = ['RAG']

brad = Agent(interactive=False, tools=TOOL_MODULES)
PATH_TO_OUTPUT_DIRECTORIES = brad.state['config'].get('log_path')

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_log_for_process_display(chat_history):
    passed_log_stages = [
        ('RAG-R', ['source 1', 'source 2', 'source 3']),
        ('RAG-G', ['This is chunk 1', 'This is chunk 2', 'This is chunk 3'])
    ]
    for i in range(len(chat_history)):
        if chat_history[i][1] is not None:
            # print('replacing logs')
            # print(f"{chat_history=}")
            chat_history[i] = (chat_history[i][0], passed_log_stages)
            # print(f"{chat_history=}")
    return chat_history # passed_log_stages

@app.route("/invoke", methods=['POST'])
def invoke_request():
    request_data = request.json
    brad_query = request_data.get("message")
    brad_response = brad.invoke(brad_query)

    # TODO: properly parse brad chatlog based on the RAG. This is left 
    #       hardcoded to demonstrate the feature.
    agent_response_log = brad.chatlog[list(brad.chatlog.keys())[-1]]
    passed_log_stages = passed_log_stages = [
        ('RAG-R', ['source 1', 'source 2', 'source 3']),
        ('RAG-G', ['This is chunk 1', 'This is chunk 2', 'This is chunk 3'])
    ]
    
    response_data = {
        "response": brad_response,
        "response-log": passed_log_stages
    }
    return jsonify(response_data)

@app.route("/rag_upload", methods=['POST'])
def upload_file():
    file_list = request.files.getlist("rag_files")
    # Creates new folder with the current statetime
    timestr = time.strftime("%Y%m%d-%H%M%S")
    directory_with_time = os.path.join(app.config['UPLOAD_FOLDER'], timestr) 
    if not os.path.exists(directory_with_time):
        os.makedirs(directory_with_time)

    for file in file_list:
        if file.filename == '':
            response = {"message": "no uploaded file"}
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_location = os.path.join(directory_with_time, filename) 
            file.save(file_location)
            response = {"message": "File uploaded successfully"}

    print("File uploads done")
    # creating chromadb with uploaded data
    print("running database creation")
    create_database(docsPath=directory_with_time, dbPath=DATABASE_FOLDER, v=True)
    return jsonify(response)

@app.route("/open_sessions", methods=['GET'])
def get_open_sessions():
    """
    This endpoint lets the front end access previously opened chat sessions.
    """
    # Auth: Joshua Pickard
    #       jpic@umich.edu
    # Date: October 14, 2024

    # Get path to output directories
    path_to_output_directories = brad.state['config']['log_path']
    
    # Get list of directories at this location
    try:
        open_sessions = [name for name in os.listdir(path_to_output_directories) 
                         if os.path.isdir(os.path.join(path_to_output_directories, name))]
        
        # Return the list of open sessions as a JSON response
        message = jsonify({"open_sessions": open_sessions})
        return message
    
    except FileNotFoundError:
        return jsonify({"error": "Directory not found"})
    
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/remove_session", methods=['POST'])
def remove_open_sessions():
    # Auth: Joshua Pickard
    #       jpic@umich.edu
    # Date: October 15, 2024

    # Parse the request data
    request_data = request.json
    session_name = request_data.get("message")  # Get the session name from the request body

    # Log the incoming request
    logger.info(f"Received request to remove session: {session_name}")

    if not session_name:
        logger.error("No session name provided in the request.")
        return jsonify({"success": False, "message": "No session name provided."}), 400

    path_to_output_directories = PATH_TO_OUTPUT_DIRECTORIES

    # Validate the log path
    if not path_to_output_directories:
        logger.error("Log path is not set in the configuration.")
        return jsonify({"success": False, "message": "Log path not configured."}), 500

    session_path = os.path.join(path_to_output_directories, session_name)

    # Check if the session directory exists
    if not os.path.exists(session_path):
        logger.warning(f"Session '{session_name}' does not exist at path: {session_path}")
        return jsonify({"success": False, "message": f"Session '{session_name}' does not exist."}), 404

    # Try to remove the session directory
    try:
        shutil.rmtree(session_path)
        logger.info(f"Successfully removed session: {session_name}")
        return jsonify({"success": True, "message": f"Session '{session_name}' removed."}), 200

    except PermissionError as e:
        logger.error(f"Permission denied while trying to remove session '{session_name}': {str(e)}")
        return jsonify({"success": False, "message": f"Permission denied: {str(e)}"}), 403

    except FileNotFoundError as e:
        logger.error(f"Session '{session_name}' not found during deletion: {str(e)}")
        return jsonify({"success": False, "message": f"Session not found: {str(e)}"}), 404

    except Exception as e:
        logger.error(f"An error occurred while trying to remove session '{session_name}': {str(e)}")
        return jsonify({"success": False, "message": f"Error removing session: {str(e)}"}), 500

@app.route("/change_session", methods=['POST'])
def change_session():
    # Auth: Joshua Pickard
    #       jpic@umich.edu
    # Date: October 15, 2024

    request_data = request.json
    print(f"{request_data=}")
    session_name = request_data.get("message")  # Get the session name from the request body
    print(f"{session_name=}")

    # Log the incoming request
    logger.info(f"Received request to change session to: {session_name}")

    if not session_name:
        logger.error("No session name provided in the request.")
        return jsonify({"success": False, "message": "No session name provided."}), 400

    path_to_output_directories = PATH_TO_OUTPUT_DIRECTORIES

    # Validate the log path
    if not path_to_output_directories:
        logger.error("Log path is not set in the configuration.")
        return jsonify({"success": False, "message": "Log path not configured."}), 500

    session_path = os.path.join(path_to_output_directories, session_name)

    # Check if the session directory exists
    if not os.path.exists(session_path):
        logger.warning(f"Session '{session_name}' does not exist at path: {session_path}")
        return jsonify({"success": False, "message": f"Session '{session_name}' does not exist."}), 404

    # Try to remove the session directory
    try:
        brad = Agent(interactive=False,
                     tools=TOOL_MODULES,
                     restart=session_path
                     )
        logger.info(f"Successfully changed to: {session_name}")
        chat_history = brad.get_display()
        chat_history = parse_log_for_process_display(chat_history)
        print("Dumb Chat History")
        print(json.dumps(chat_history, indent=4))
        response = jsonify({
            "success": True,
            "message": f"Session '{session_name}' activated.",
            "display": chat_history
            }
        )
        return response, 200

    except PermissionError as e:
        logger.error(f"Permission denied while trying to change session '{session_name}': {str(e)}")
        return jsonify({"success": False, "message": f"Permission denied: {str(e)}"}), 403

    except FileNotFoundError as e:
        logger.error(f"Session '{session_name}' not found during session change: {str(e)}")
        return jsonify({"success": False, "message": f"Session not found: {str(e)}"}), 404

    except Exception as e:
        logger.error(f"An error occurred while trying to change session: '{session_name}': {str(e)}")
        return jsonify({"success": False, "message": f"Error changing session: {str(e)}"}), 500
