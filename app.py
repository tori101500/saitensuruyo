import streamlit as st
import requests

# Gemini APIのエンドポイント
GEMINI_API_URL = "https://api.gemini.com/v1/grade"

def grade_submission(api_key, submission_text):
    """
    Gemini APIを利用して採点を行う関数
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "submission": submission_text
    }

    try:
        response = requests.post(GEMINI_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

# StreamlitアプリのUI
def main():
    st.title("自動採点アプリ")
    st.write("Gemini APIを利用して提出物を自動採点します。")

    # ユーザー入力
    submission_text = st.text_area("採点対象のテキストを入力してください", height=200)

    if st.button("採点を実行"):
        if not submission_text.strip():
            st.error("テキストを入力してください。")
        else:
            st.info("採点中です...")
            api_key = st.secrets["GEMINI_API_KEY"]
            result = grade_submission(api_key, submission_text)

            if "error" in result:
                st.error(f"エラーが発生しました: {result['error']}")
            else:
                st.success("採点が完了しました！")
                st.json(result)

if __name__ == "__main__":
    main()