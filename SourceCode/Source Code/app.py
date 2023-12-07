import pandas as pd
import streamlit as st
from PIL import Image
import os
import json
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema.output_parser import StrOutputParser
from langchain.schema.runnable import RunnablePassthrough
import requests
from dotenv import load_dotenv
import subprocess

# Vars
filename = "user_info.csv"
csv_path = ("/Database/user_info.csv")
load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")
google_maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")

# Set title
st.title("Dev300 - Dynamic Alarm Project")
st.markdown("Fill out the form below to get started!")

# List of common morning activities
morningActivities = ["Take a shower", "Brush teeth", "Breakfast", "Change clothes", "Read a book", "Take kids to school", "Walk the dog", "Exercise", "Other"]

# Function to get user input
def user_input(morningActivities):
    with st.form(key="user_profile"):
        user_name = st.text_input("What's your name?")
        user_gender = st.selectbox("Gender", options=["Male", "Female", "Wish not to answer"], index=None)
        user_livingAdd = st.text_input("Where do you live? Please input the address, with the city, zip code and state:")
        user_workAdd = st.text_input("Where do you work? Please input the address, with the city, zip code and state:")
        user_morningRoutine = st.multiselect("What do you usually do in the mornings? Select your daily routine:", options=morningActivities)
        user_sleepT = st.time_input("What time do you usually go to sleep on work days?")
        user_wakeT = st.time_input("What time do you usually wake up on work days?")
        user_timeAtWork = st.time_input("What time do you need to be at work at?")

        submit_button = st.form_submit_button(label='Submit')

        if submit_button:
            st.write("Thank you for submitting your information!")
            
            # Create a dictionary with the user's info
            user_info = pd.DataFrame({
                "name": [user_name.rstrip()],
                "gender": [user_gender],
                "livingAdd": [user_livingAdd.rstrip()],
                "workAdd": [user_workAdd.rstrip()],
                "morningRoutine": [", ".join(user_morningRoutine)],
                "sleepT": [user_sleepT],
                "wakeT": [user_wakeT],
                "timAtWork": [user_timeAtWork]
            })

            return user_info

# Function to append the user's info to a CSV file
def append_to_csv(user_info, filename):
    # If the file doesn't exist yet, write the header (column names) to the file
    if not os.path.isfile(filename):
        user_info.to_csv(filename, mode='a', index=False)
    else:
        # If the file exists, append the data without writing the header
        user_info.to_csv(filename, mode='a', index=False, header=False)

# Get info from the database for the user 'x' and store it in a dictionary
def get_user_info():
    # Read the csv file
    df = pd.read_csv(csv_path)

    # Get the last row with the user's info
    user_info = df.iloc[-1]

    # Convert the row into a dictionary
    user_info_dict = user_info.to_dict()

    return user_info_dict

# Function to get the ETA from Google Maps Directions API
def get_eta(home_address, work_address, api_key):
    # Encode the addresses to be URL-friendly
    home_address_encoded = requests.utils.quote(home_address)
    work_address_encoded = requests.utils.quote(work_address)

    # Construct the Google Maps Directions API request URL
    directions_url = f"https://maps.googleapis.com/maps/api/directions/json?origin={home_address_encoded}&destination={work_address_encoded}&key={api_key}"

    # Make the request to the Google Maps API
    response = requests.get(directions_url)

    # Check if the request was successful
    if response.status_code == 200:
        directions_data = response.json()
        
        # Make sure the API returned routes
        if directions_data['status'] == 'OK':
            # Extract the travel duration in traffic if available
            # Otherwise, use the standard travel duration
            legs = directions_data['routes'][0]['legs'][0]
            duration_in_traffic = legs.get('duration_in_traffic', legs['duration'])
            eta_seconds = duration_in_traffic['value']  # Duration in seconds
            
            # Convert ETA from seconds to a more readable format
            eta_minutes = eta_seconds // 60
            return eta_minutes
        else:
            print(f"Error: {directions_data['status']}")
            return None
    else:
        print("Failed to retrieve directions")
        return None

# Call the function to get user info (same as your existing code)
user_info = get_user_info()

# Main function
user_info = user_input(morningActivities)
if user_info is not None:
    with st.spinner('Processing...'):
        # Convert time objects to strings
        user_info['sleepT'] = user_info['sleepT'].astype(str)
        user_info['wakeT'] = user_info['wakeT'].astype(str)
        user_info['timAtWork'] = user_info['timAtWork'].astype(str)

        append_to_csv(user_info, filename)

        # Call the function to get user info (same as your existing code)
        user_info_query = get_user_info()

        # Get the ETA using the home and work addresses
        eta_minutes = get_eta(user_info_query['livingAdd'], user_info_query['workAdd'], google_maps_api_key)

        user_info_dict = user_info.to_dict('records')  # Convert DataFrame to dictionary
        user_info_str = json.dumps(user_info_dict, indent=2)  # Convert dictionary to JSON string

        #Creating langchain template

        template = """user information: {user_info} and ETA by google:{eta_minutes}

        ----------------

        Given the user's morning routine, home address, work address, and estimated travel time (ETA) from Google Maps API, determine the appropriate wake-up time to ensure the user can complete their morning routine and reach work on time. Take into account the fixed duration of each task in the morning routine, the user's usual wake-up time, and the time they need to be at work. You should adjust the wake-up time if necessary, based on the current ETA and total duration of the morning routine, do not assume the ETA, instead use the value provided. The goal is to provide a wake-up time that ensures punctuality without disrupting the user's usual schedule more than necessary.

        ----------------"""

        template_prompt = ChatPromptTemplate.from_template(template)

        chain = RunnablePassthrough.assign(
            text=lambda x: user_info_str, 
        ) | template_prompt | ChatOpenAI(model="gpt-4-1106-preview", openai_api_key=openai_api_key) | StrOutputParser()

        # Invoke the chain and get the output
        output = chain.invoke(
            {
                'user_info': user_info_str,
                'eta_minutes': eta_minutes,
                'question': "How should I adjust my wake-up time? If I have to change my alarm, use the following format: 'Change alarm to 7:30 AM' or 'No change needed'"
            }
        )

    st.text_area("GTP-4 Logic of User's Routine:", output, height=500)

        # Create a second template
    template2 = """Analyse the first response: {first_response}

        ----------------

        Based on the first response, provide me with a boolean value and the new wake-up time if any is recommended. If the user needs to change their alarm, use the following format: 'TRUE, 7:30am' or 'FALSE'

        ----------------"""

    template_prompt2 = ChatPromptTemplate.from_template(template2)

    chain2 = RunnablePassthrough.assign(
            text=lambda x: output, 
        ) | template_prompt2 | ChatOpenAI(model="gpt-4-1106-preview", openai_api_key=openai_api_key) | StrOutputParser()

        # Invoke the second chain and get the output
    output2 = chain2.invoke(
            {
                'first_response': output,
                'question': "Let me know if the user needs to change their alarm. "
            }
        )

    st.info("Parser:\n" + output2)

    # Parse the output2 string to get the boolean value and the new wake-up time
    output2_split = output2.split(", ")
    change_alarm = output2_split[0] == "TRUE"
    new_wake_up_time = output2_split[1] if change_alarm else None

    if change_alarm:
        subprocess.run(["./setAlarm.sh", new_wake_up_time])

        # Display a message in the Streamlit UI
        st.success(f"Alarm has been set to {new_wake_up_time}.")
    else:
        # Display a message in the Streamlit UI
        st.info("Nothing to change, you should be all set!")