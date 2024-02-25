import argparse
import re
from time import sleep

import yaml
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.remote.webelement import WebElement
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
        self.seating_search_type: str = "Centre"
        self.skip_all_before_disabled: bool = True
        self.seat_amount: int = 1
        self.seat_tolerance_offset: int = 2

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
    driver.implicitly_wait(2)

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
                check_sessions(driver, args=args)
                break

    sleep(1)
    driver.quit()


def check_sessions(driver: webdriver.Firefox, args: InputArgs):
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

            session_validity = (
                "VALID"
                if is_session_valid(driver, args, session_element)
                else "INVALID"
            )
            print(
                f"Found session for: {time.text} in {tag.text} and it's {session_validity}"
            )
            sleep(1)  # Wait for modal to close

    pass


def is_session_valid(
    driver: webdriver.Firefox, args: InputArgs, session_element: WebElement
):
    # Click on the session to get the seating modal
    session_element.click()

    # NOTE: Each seating row is a class of 'seating-map__row', each row has a letter span
    # with class 'seating-map__letter', including invalid rows, but they'll have no content in the span.
    # NOTE: rows with 'disabled' seating can be worked out by finding a seat within the row that has an
    # svg with the text contents containing '#icon-seat-wheelchair'

    starting_row_letter: str = "A"
    seating_map_element = driver.find_element(By.CLASS_NAME, "seating-map__overflow")
    sleep(1)

    # Determine the starting row letter if the user wants to skip all rows before the disabled row
    if args.skip_all_before_disabled:
        found_disabled: bool = False

        # Find the disabled row
        for row in seating_map_element.find_elements(By.CLASS_NAME, "seating-map__row"):
            row_letter = row.find_element(By.CLASS_NAME, "seating-map__letter")

            if found_disabled:
                print(f"Found disabled row: {starting_row_letter}")
                break

            if row_letter.text.strip() != "":
                # Search the row for a disabled seat
                row_seats = row.find_elements(By.CLASS_NAME, "seating-map__seat")
                for seat in row_seats:
                    innerhtml = seat.get_attribute("innerHTML") or ""
                    if "#icon-seat-wheelchair" in innerhtml:
                        found_disabled = True
                        starting_row_letter = row_letter.text
                        break
    # Build an array of all the seats
    start_building_matrix: bool = False
    seating_matrix: list[list[int]] = []
    seating_matrix_elements: list[list[WebElement]] = []
    for row in seating_map_element.find_elements(By.CLASS_NAME, "seating-map__row"):
        row_letter = row.find_element(By.CLASS_NAME, "seating-map__letter").text
        if row_letter == "":
            continue

        if row_letter == starting_row_letter:
            start_building_matrix = True
            continue

        # Skip all rows before the disabled row (if the user wants to)
        if row_letter != starting_row_letter and not start_building_matrix:
            continue

        # Build the matrix
        row_seats = row.find_elements(By.CLASS_NAME, "seating-map__seat")
        row_matrix: list[int] = []
        row_matrix_elements: list[WebElement] = []
        for seat in row_seats:
            # NOTE: Seats that are taken contain a button with class 'is-reserved', seats that are disabled
            # contain a button with class 'is-unavailable', and seats that are available contain a button with
            # no class.
            row_matrix_elements.append(seat)
            seat_innerhtml = seat.get_attribute("innerHTML") or ""

            if "is-reserved" in seat_innerhtml.lower():
                # print("Reserved seat found!")
                row_matrix.append(1)
            elif "is-unavailable" in seat_innerhtml.lower():
                # print("Unavailable seat found!")
                row_matrix.append(2)
            elif "seating-map__button" in seat_innerhtml.lower():
                # print("Available seat found!")
                row_matrix.append(0)
            else:
                row_matrix.append(2)

        seating_matrix.append(row_matrix)
        seating_matrix_elements.append(row_matrix_elements)

    # Determine if session can fit the amount of seats requested
    # Build amount of seats array that is 0's for the amount of seats requested
    amount_of_seats: list[int] = [0] * args.seat_amount
    tolerance: int = args.seat_tolerance_offset

    # TODO: Just handle centre seating for now
    print("Checking for seating!")
    if args.seating_search_type.lower() == "centre":
        # Get the centre of the matrix
        centre_row: int = len(seating_matrix) // 2
        row_offset: int = 0
        centre_column: int = len(seating_matrix[0]) // 2

        # Start from the centre row and work outwards
        while (centre_row + row_offset) < len(seating_matrix) and (
            centre_row - row_offset
        ) >= 0:
            for i in range(centre_column - tolerance, centre_column + tolerance):
                # Check row above
                if not (centre_row + row_offset >= len(seating_matrix)):
                    # seating_matrix_elements[centre_row + row_offset][i].click()
                    if (
                        seating_matrix[centre_row + row_offset][
                            i : i + args.seat_amount
                        ]
                        == amount_of_seats
                    ):
                        # Close the modal
                        driver.find_element(By.CLASS_NAME, "ticketing__close").click()
                        return True

                if row_offset != 0:
                    if (centre_row - row_offset) >= 0:
                        # seating_matrix_elements[centre_row - row_offset][i].click()
                        if (
                            seating_matrix[centre_row - row_offset][
                                i : i + args.seat_amount
                            ]
                            == amount_of_seats
                        ):
                            # Close the modal
                            driver.find_element(
                                By.CLASS_NAME, "ticketing__close"
                            ).click()
                            return True
            row_offset += 1
    # Close the modal
    driver.find_element(By.CLASS_NAME, "ticketing__close").click()
    return False


def class_exists(inner_html, class_name):
    return bool(re.search(f"class=[\"'].*\b{class_name}\b.*[\"']", inner_html))


def does_element_exist(parent: WebElement, by: str, value: str) -> bool:
    print(f"Checking for element: {value} using {by}!")
    try:
        parent.find_element(by, value)
        print(f"Element: {value} exists!")
        return True
    except NoSuchElementException:
        print(f"Element: {value} does not exist!")
        return False


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
    parser.add_argument(
        "--seating-search-type",
        type=str,
        help="Seating type to determine the best session time\n Valid options: 'left', 'centre', 'right', 'all'",
    )
    parser.add_argument(
        "--seat-amount",
        type=int,
        help="Amount of seats to arrange for",
    )
    parser.add_argument(
        "--skip-all-before-disabled",
        type=bool,
        help="Skip all rows before the disabled row. (this is typically too close)",
    )
    parser.add_argument(
        "--seating-tolerance-offset",
        type=int,
        help="How far from the centre of a row to search for seating. (default: 2)",
    )
    namespace = InputArgs()
    return parser.parse_args(namespace=namespace)


if __name__ == "__main__":
    # Pass command line arguments to main
    main()
