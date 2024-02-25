import argparse
from time import sleep

import yaml
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager

HOYTS_BASE_URL = "https://hoyts.com.au"
HOYTS_MOVIES_URL = f"{HOYTS_BASE_URL}/movies/"

THEATRE_CONFIG_LOCAITON = "theatres"

NUM_TO_MONTH = [
    "JAN",
    "FEB",
    "MAR",
    "APR",
    "MAY",
    "JUN",
    "JUL",
    "AUG",
    "SEP",
    "OCT",
    "NOV",
    "DEC",
]


class InputArgs(argparse.Namespace):
    def __init__(self):
        self.movie: str = ""
        self.locations: list[str] = []
        self.headless: bool = False
        self.dates: list[str] = []

    def __str__(self):
        return f"Movie: {self.movie}, locations: {self.locations}"


# Entry point
def main():
    # Handle command line arguments
    args: InputArgs = parse_args()

    # Validate arguments
    if len(args.movie.strip()) == 0:
        print("Please provide a movie name")
        return

    if len(args.locations) <= 0:
        print("Please provide a location")
        return

    if len(args.dates) <= 0:
        print("Please provide a session times")
        return

    # Get starting page
    MOVIE_URL = f"{HOYTS_MOVIES_URL}{args.movie}"
    # page = requests.get(URL)
    # soup = BeautifulSoup(page.content, "html.parser")

    # Setup selenium
    driver_options = webdriver.FirefoxOptions()
    if args.headless:
        driver_options.add_argument("--headless")
    driver_options.add_argument("--incognito")
    driver = webdriver.Firefox(
        options=driver_options,
        service=FirefoxService(GeckoDriverManager().install()),
    )

    # Set implicit wait
    driver.implicitly_wait(5)

    # Visually see the browser
    # if not args.headless:
    #     driver.maximize_window()

    # Get starting page
    driver.get(MOVIE_URL)

    ## SELECT LOCATIONS ##

    # Open the side bar
    button = driver.find_element(
        By.CSS_SELECTOR, "button.widget__subheading.widget__subheading--button"
    )
    button.click()

    # Click on the 'Add Cinema' button, and select all the locations
    state_buttons = driver.find_elements(By.CLASS_NAME, "modal__tab-text")

    # Select all the desired locations
    for location in args.locations:
        # Read the YAML file for the location
        with open(f"{THEATRE_CONFIG_LOCAITON}/{location}.yaml", "r") as file:
            loaded_yaml = yaml.load(file, Loader=yaml.FullLoader)
            yaml_state = loaded_yaml["state"]

            # Click the relevant state tab
            for state in state_buttons:
                if state.text.lower() == yaml_state.lower():
                    print(f"Clicking on State: {yaml_state}")
                    state.click()

                    # Loop through the cinemas and select the current location
                    cinemas = driver.find_elements(
                        By.CLASS_NAME, "modal__item-checkbox"
                    )
                    for cinema in cinemas:
                        if cinema.text.lower() == location.lower():
                            print(f"Clicking on Location: {location}")
                            cinema.click()
                            break
                    break

    # Click the 'Save & Browse' button
    save_button = driver.find_element(By.CLASS_NAME, "modal__save-button")
    save_button.click()
    sleep(1)  # Wait for the page to load

    ## SESSION TIMES ##

    for date in args.dates:
        # Convert DD-MM to int day and str month
        day, month = date.split("-")
        day = int(day)
        month = NUM_TO_MONTH[int(month) - 1]

        # Click the date button
        dates_element_wrapper = driver.find_element(By.CLASS_NAME, "swiper-wrapper")
        date_elements = dates_element_wrapper.find_elements(
            By.CLASS_NAME, "swiper-slide"
        )

        for date_button in date_elements:
            # Validate if the session
            if f"{day} {month}" in date_button.text:
                print(f"Clicking on date: {date_button.text}")
                date_button.click()
                # TODO: NEED TO LOOK FOR SESSION TIMES IN HERE, OTHERWISE IT WILL JUST CLICK ON THE LAST DATE
                check_sessions(driver)
                break

    sleep(3)
    driver.quit()


def check_sessions(driver: webdriver.Firefox):
    session_groups = driver.find_elements(By.CLASS_NAME, "sessions")

    # Each session group is for each different location
    for session_group in session_groups:
        # Get the location name
        location = session_group.find_element(By.CLASS_NAME, "sessions__heading")
        print(f"Checking sessions for Location: {location.text}")

        # Get all the session times
        sessions = session_group.find_element(
            By.CLASS_NAME, "sessions__list"
        ).find_elements(By.CLASS_NAME, "sessions__item")

        # Loop through the sessions
        for session_element in sessions:
            time = session_element.find_element(By.CLASS_NAME, "session__time")
            tag = session_element.find_element(By.CLASS_NAME, "session__tag")
            print(f"Found session for: {time.text} in {tag.text}")
    pass


def parse_args():
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("--movie", type=str, help="Movie to search for")
    parser.add_argument(
        "--locations",
        type=lambda s: [item for item in s.split(",")],
        help="Locations to search for (comma separated)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run the browser in headless mode (no GUI)",
    )
    parser.add_argument(
        "--dates",
        type=lambda s: [item for item in s.split(",")],
        help="Dates to search for in the form of 'dd-mm' (comma separated)",
    )
    namespace = InputArgs()
    return parser.parse_args(namespace=namespace)


if __name__ == "__main__":
    # Pass command line arguments to main
    main()
