from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import logging
import json

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet

from zomato.zomato_api import Zomato


# Import the email modules we'll need to send messages
import smtplib
from email.message import EmailMessage

logger = logging.getLogger("__name__")
user_key = ""
config = {"user_key": user_key}
_zomato = Zomato(config)


class ActionSearchRestaurants(Action):
    def name(self):
        return "action_restaurant"

    def run(self, dispatcher, tracker, domain):

        restaurants_found = []
        response_message = ""

        location = tracker.get_slot("location")
        cuisine = tracker.get_slot("cuisine")

        if not location:
            dispatcher.utter_template("utter_ask_location", tracker)
        else:
            """
				retrieve location details
			"""
            response = _zomato.get_location(location)
            location_details = {}

            if response is not None:
                response_json = json.loads(response)
                if response_json["status"] == "success":
                    """
						fetch location details and store 'city_id'
					"""
                    location_details = response_json["location_suggestions"][0]
                    city_id = location_details["city_id"]

                    """
						fetch all cuisines available in the location
					"""
                    response_cuisine = _zomato.get_cuisines(city_id)
                    supported_cuisines = [
                        "American",
                        "Chinese",
                        "Italian",
                        "Mexican",
                        "North Indian",
                        "South Indian",
                    ]
                    filtered_cuisine = {
                        key: value
                        for key, value in response_cuisine.items()
                        if value in supported_cuisines
                    }

                    if cuisine is not None:
                        cuisine_list = [
                            key
                            for key, value in filtered_cuisine.items()
                            if str(value).lower() == cuisine.lower()
                        ]
                    else:
                        cuisine_list = [key for key, value in filtered_cuisine.items()]

                    restaurants_found = self.search_restaurant(
                        location, location_details, cuisine_list
                    )

                    if len(restaurants_found) > 0:
                        for restaurant in restaurants_found:
                            response_message = (
                                response_message
                                + "Found "
                                + restaurant["name"]
                                + " in "
                                + restaurant["address"]
                                + "with average rating "
                                + restaurant["rating"]
                                + "\n"
                            )
                    else:
                        response_message = "no results"
            else:
                dispatcher.utter_message("no results")

        dispatcher.utter_message(response_message)

        return [SlotSet("location", location)]

    def search_restaurant(
        self, location="", location_details={}, cuisine_list=[]
    ) -> list:
        restaurants_found = []

        """
			Search restaurants
		"""
        response = _zomato.restaurant_search(
            location,
            location_details["latitude"],
            location_details["longitude"],
            cuisine_list,
            location_details["city_id"],
            "city",
        )

        if response is not None:
            response_json = json.loads(response)
            if response_json["results_found"] > 0:
                for restaurant in response_json["restaurants"]:
                    restaurants_found.append(
                        {
                            "name": restaurant["restaurant"]["name"],
                            "address": restaurant["restaurant"]["location"]["address"],
                            "avg_cost_for_2": restaurant["restaurant"]["average_cost_for_two"],
                            "rating": restaurant["restaurant"]["user_rating"]["aggregate_rating"],
                        }
                    )

        return restaurants_found


class ActionSendEmail(Action):

    def name(self):
        return "action_sendemail"

    def run(self, dispatcher, tracker, domain):
        location = tracker.get_slot("location")
        emailid = tracker.get_slot("email")
        msg = EmailMessage()
        msg.set_content(tracker.latest_message.text)
        msg['Subject'] = 'The List of Restaurants you requested for %s' %location
        myvars = {}
        with open("smtpconfig.txt") as mailfile:
            for line in mailfile:
                name, var = line.partition("=")[::2]
                myvars[name.strip()] = var.strip()
		# Send the message via SMTP server.
        s = smtplib.SMTP(host=myvars["smtpserver_host"], port=myvars["smtpserver_port"])
        s.login(myvars["username"], myvars["password"]
        msg['From'] = myvars["from_email"]
        msg['To'] = emailid
        s.send_message(msg)
        s.quit()
        dispatcher.utter_message("I have sent the email with the list of restaurants")