import pprint
from llm_n.hybrid_pipeline import process_entries


def main():
    summary = process_entries()
    pprint.pprint(summary)


if __name__ == "__main__":
    main()
