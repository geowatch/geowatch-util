"""
Contains the base GeoWatchBroker class
"""
import time


class GeoWatchBroker(object):
    """
    Base broker class.  This class can pass messages among consumers, producers, and stores.
    If you wish to add more advanced logic, extend the class and overwrite the _pre and _post functions.
    """

    verbose = False
    name = None
    description = None

    threads = None
    sleep_period = None
    deduplicate = False
    count = 1
    timeout = 5

    # Filters
    filter_metadata = None
    filter_last_one = False  # Filter messages to only last/latest message

    # Streaming
    consumers = None
    producers = None
    duplex = None

    # Batch
    stores_in = None
    stores_out = None

    def receive_message(self, message=None, filter_messages=True):
        self.receive_messages(messages=[message], filter_messages=filter_messages)

    def receive_messages(self, messages=None, filter_messages=True):
        if filter_messages:
            messages = self._cycle_filter(messages)
        self._cycle_out(messages=messages)
        self._post(messages=messages)

    def _pre(self):
        pass

    def _post(self, messages=None):
        pass

    def run(self, max_cycle=0, run_cycle_out=True):
        cycle = 1
        while True:
            if self.verbose:
                print "Cycle: ", cycle

            self._pre()

            messages = self._cycle_in()

            messages = self._cycle_filter(messages)

            if run_cycle_out:
                self._cycle_out(messages=messages)

            self._post(messages=messages)

            if max_cycle > 0 and cycle == max_cycle:
                break

            cycle += 1
            time.sleep(self.sleep_period)

    def _cycle_in(self):
        if self.verbose:
            print "GeoWatchBroker._cycle_in()"
        messages_all = []
        messages_out = []

        if self.stores_in:
            for store in self.stores_in:
                messages = store.read()
                if messages:
                    messages_all.extend(messages)

        if self.consumers:
            if self.verbose:
                print "Receiving messages from "+str(len(self.consumers))+" consumers."
            for consumer in self.consumers:
                messages_all = self.cycle_in_consumer(consumer, messages_all)

        if self.duplex:
            if self.verbose:
                print "Receiving messages from "+str(len(self.consumers))+" duplex nodes."
            for consumer in self.duplex:
                messages_all = self.cycle_in_consumer(consumer, messages_all)

        if self.verbose:
            print "Processing "+str(len(messages_all))+" messages."

        if self.deduplicate:
            seen = set()
            for message in messages_all:
                if message not in seen:
                    seen.add(message)
                    messages_out.append(message)
            if self.verbose:
                print str(len(messages_out))+" unique messages out of "+str(len(messages_all))+" messages."
        else:
            messages_out = messages_all

        return messages_out

    def cycle_in_consumer(self, consumer, messages_all):
        left = self.count - len(messages_all)
        if left > 0:
            messages = consumer.get_messages(left, timeout=self.timeout)
            # Returns messages encoded, such as list of strings, dicts/json, etc.
            if messages:
                messages_all.extend(messages)
        return messages_all

    def _cycle_filter(self, messages=None):
        if self.filter_metadata:
            messages_filtered = []
            for message in messages:
                valid = True
                if "metadata" in messages:
                    for k in self.filter_metadata:
                        if messages["metadata"][k] not in self.filter_metadata[k]:
                            valid = False
                            break

                if valid:
                    messages_filtered.append(message)
        else:
            messages_filtered = messages

        if self.filter_last_one:
            messages_filtered = [messages_filtered[-1]]

        return messages

    def _cycle_out(self, messages=None):
        if messages:
            if self.producers:
                for producer in self.producers:
                    producer.send_messages(messages)
            if self.duplex:
                for producer in self.duplex:
                    producer.send_messages(messages)
            if self.stores_out:
                for store in self.stores_out:
                    store.write_messages(messages, flush=True)

    def delete_topics(self):
        """
        Deletes all topics attached to consumers and producers.  Useful for cleaning up after testing.
        """
        if self.consumers:
            for consumer in self.consumers:
                consumer.delete_topic()
        if self.producers:
            for producer in self.producers:
                producer.delete_topic()
        if self.duplex:
            for node in self.duplex:
                node.delete_topic()


    def close(self):
        for producer in self.producers:
            producer.close()
        for store in self.stores_out:
            store.close()

    def __init__(self, name, description, consumers=None, producers=None, duplex=None, stores_in=None, stores_out=None, count=1, timeout=5, threads=1, sleep_period=5, deduplicate=False, filter_metadata=None, filter_last_one=False, verbose=False):
        self.name = name
        self.description = description
        self.consumers = consumers
        self.producers = producers
        self.duplex = duplex
        self.stores_in = stores_in
        self.stores_out = stores_out
        self.count = count
        self.timeout = timeout
        self.threads = threads
        self.sleep_period = sleep_period
        self.deduplicate = deduplicate
        self.filter_metadata = filter_metadata
        self.filter_last_one = filter_last_one

        self.verbose = verbose

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.close()
