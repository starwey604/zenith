"""Compatibility command: pickup screening now ends when ore clears the edge."""

from .pickup_exit import main, screen_pickup_exit

screen_pickup_recovery = screen_pickup_exit


if __name__ == "__main__":
    main()
