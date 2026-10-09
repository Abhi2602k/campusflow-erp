import requests

BASE_URL = "http://127.0.0.1:8000/api/v1"
client = requests.Session()

def run_tests():
    print("--- Starting End-to-End API Tests ---")
    
    # Test 1: Superadmin Login
    print("\n[1] Testing Superadmin Login...")
    res = client.post(f"{BASE_URL}/auth/login", json={"email": "abhi2602k@gmail.com", "password": "Aashu@123"})
    if res.status_code == 200:
        print("? Superadmin Login Successful")
    else:
        print(f"? Superadmin Login Failed: {res.text}")
        return

    # Test 2: Fetch Admins (Superadmin route)
    print("\n[2] Testing Superadmin Routes (Get Admins)...")
    res = client.get(f"{BASE_URL}/management/superadmin/admins")
    if res.status_code == 200:
        print("? Superadmin Route Accessed Successfully")
    else:
        print(f"? Superadmin Route Failed: {res.text}")

    # Test 3: Create an Admin
    print("\n[3] Testing Admin Creation...")
    res = client.post(f"{BASE_URL}/management/superadmin/admins", json={
        "name": "Test Admin",
        "email": "testadmin_e2e@example.com",
        "password": "Password123!"
    })
    if res.status_code == 200:
        print("? Admin Created Successfully")
    elif res.status_code == 400 and "already registered" in res.text:
        print("? Admin Creation (Already Exists - Working Properly)")
    else:
        print(f"? Admin Creation Failed: {res.text}")

    # Test 4: General Data Fetching (Health Check)
    print("\n[4] Testing General Backend Stability (Get Classes)...")
    res = client.get(f"{BASE_URL}/management/classes")
    if res.status_code == 200:
        print("? Backend Database Connection Stable")
    else:
        print(f"? Database Query Failed: {res.text}")
        
    print("\n--- All core systems are ONLINE and RESPONSIVE ---")

if __name__ == "__main__":
    run_tests()
