import argparse
import json
import os
import random
from urllib.request import Request, urlopen
from uuid import NAMESPACE_URL, uuid5

API = os.environ.get("BANKING_API_URL", "http://api:8000").rstrip("/")


def rows(count: int, seed: int) -> list[dict]:
    randomizer = random.Random(seed)
    return [
        {
            "transaction_id": str(uuid5(NAMESPACE_URL, f"banking/{seed}/{index}")),
            "account_id": str(uuid5(NAMESPACE_URL, f"banking/account/{index % 12}")),
            "amount_minor": randomizer.randint(100, 100000),
            "currency": ("USD", "INR", "EUR")[index % 3],
        }
        for index in range(count)
    ]


def send(method: str, path: str, body: dict | None = None) -> dict:
    request = Request(API + path, method=method,
                      data=None if body is None else json.dumps(body).encode(),
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=15) as response:
        return {} if response.status == 204 else json.load(response)


def generate(count: int, seed: int, scenario: str) -> None:
    for index, row in enumerate(rows(count, seed)):
        path = "/transactions/" + row["transaction_id"]
        if scenario == "create":
            send("POST", "/transactions", row)
        else:
            if index % 10 == 0:
                send("DELETE", path + "?expected_version=1")
                continue
            result = send("PATCH", path, {
                "expected_version": 1, "amount_minor": row["amount_minor"] + 13,
                "status": ("settled", "failed", "cancelled")[index % 3],
            })
            if index % 7 == 0 and result["status"] == "settled":
                send("PATCH", path, {"expected_version": 2, "status": "reversed"})
    print(f"scenario={scenario} seed={seed} transactions={count}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", choices=["create", "mutate"])
    parser.add_argument("--count", type=int, default=120)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if not 1 <= args.count <= 1000:
        parser.error("--count must be between 1 and 1000")
    generate(args.count, args.seed, args.scenario)


if __name__ == "__main__":
    main()
