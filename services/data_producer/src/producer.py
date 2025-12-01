import time

if __name__ == "__main__":
    print("Data producer service started.")
    # In the future, this will produce messages to Kafka.
    while True:
        print("Producing data...")
        time.sleep(10)
