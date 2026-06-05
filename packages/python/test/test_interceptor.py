from zgrc import init
from dotenv import load_dotenv
import requests

load_dotenv()

init(
    api_key="grc_eNp1zUEOgyAQRuG7zNpRGAgD3gblj5o0oal0o-ndy66rrr-XvJveR6GZjE2IkgtLgmdNEjghGHYW3kOLijgaaK9n6_Xe2vOcp-ni7bWOF5ZxrV1rw-O_br9RCZltLpFVkThaGF4cXOwjqHr6fAGjsiry"
)

url = "https://z-grc.zeb.co/api/quota/user?group_id=019e924c-434a-773c-8ae4-aefb26867278&user_id=019e82ad-29e4-7926-9e60-31e44e7d7223"
response = requests.get(url)

if __name__ == "__main__":
    if response.status_code == 200:
        # Parse the response payload into a Python dictionary
        data = response.json()
        print("Success!")
        print(data)
    else:
        print(f"Failed to retrieve data. Status code: {response.status_code}")
