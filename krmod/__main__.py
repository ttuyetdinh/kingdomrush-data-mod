"""Main entry point for `python -m krmod`."""
import multiprocessing

if __name__ == "__main__":
    # The native window runs in a spawned child process. In the frozen exe that child
    # starts this same script, so it must hand over to multiprocessing before the app
    # module loads the game data and starts a second app.
    multiprocessing.freeze_support()
    from krmod.app import main

    main()
