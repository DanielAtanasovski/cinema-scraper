import argparse


class InputArgs(argparse.Namespace):
    def __init__(self):
        self.movie = None

    def __str__(self):
        return f"Movie: {self.movie}"


# Entry point
def main():
    # Handle command line arguments
    args: InputArgs = parse_args()

    # Validate arguments
    if not args.movie:
        print("Please provide a movie name")
        return


def parse_args():
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("--movie", type=str, help="Movie to search for")
    namespace = InputArgs()
    return parser.parse_args(namespace=namespace)


if __name__ == "__main__":
    # Pass command line arguments to main
    main()
