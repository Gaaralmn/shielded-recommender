import time

if __name__ == "__main__":
    print("Trainer service started.")
    # In the future, this will train the recommender model.
    while True:
        print("Looking for training jobs...")
        time.sleep(60)
