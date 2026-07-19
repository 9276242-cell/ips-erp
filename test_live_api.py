import urllib.request
import urllib.parse
import json

def test_login():
    url = "https://ips-erp-897055767918.us-central1.run.app/auth/login"
    data = json.dumps({"username": "admin", "password": "admin123"}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            print("Login Response Status: 200 OK")
            print("Token Returned:", res_json.get("access_token")[:15] + "...")
            print("User Role:", res_json.get("role"))
            assert res_json.get("role") == "Admin", "Role mismatch!"
            print("Test Case: Admin Login -> SUCCESS [OK]")
    except Exception as e:
        print("Admin Login -> FAILED:", e)

if __name__ == "__main__":
    test_login()
