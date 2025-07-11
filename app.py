import os, re, unicodedata, pandas as pd, streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
from PIL import Image
import gdown, zipfile, io

# ────────────────────────────────────────────────────
# ✅ 세션 상태 설정
# ────────────────────────────────────────────────────
if "start" not in st.session_state:
    st.session_state.start = False

# ────────────────────────────────────────────────────
# ✅ 랜딩 페이지
# ────────────────────────────────────────────────────
if not st.session_state.start:
    st.set_page_config(page_title="숨은 \꿀벌 찾기", layout="centered")

    logo = Image.open("Logo.png")
    st.image(logo, width=300)

    st.title("🐝 장바구니 속 숨은 꿀벌 찾기")
    st.markdown(
        "기후 변화 때문에 꿀벌 친구들이 점점 사라지고 있대요. 😢<br>"
        "그런데 꿀벌이 없으면 우리가 마트에서 장보던 좋아하는 음식들도 함께 사라질 수 있는 거 알고 있었나요? 🍫<br>"
        "우리 가족의 장바구니 안에는 어떤 꿀벌의 흔적이 남아 있을까요? 지금 함께 찾아봐요! 🔍",
        unsafe_allow_html=True
    )

    if st.button("🔍 시작하기"):
        st.session_state.start = True
        st.rerun()

# ────────────────────────────────────────────────────
# ✅ 1. 공통 정규화 함수
# ────────────────────────────────────────────────────
def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", str(text))
    text = re.sub(r"\s+", "", text)
    return text.lower()

# ────────────────────────────────────────────────────
# ✅ 2. 데이터 로드 (Google Drive ZIP 사용)
# ────────────────────────────────────────────────────
@st.cache_data
def load_data():
    zip_url = "https://drive.google.com/uc?id=1v7nNYDUl0OSmJ75PSBuOFb5bPy-aLPRt"
    gdown.download(zip_url, "merged_bee_ready.zip", quiet=False)

    with zipfile.ZipFile("merged_bee_ready.zip") as z:
        with z.open("merged_bee_ready.csv") as f:
            df = pd.read_csv(f, dtype=str, encoding='utf-8')

    mapping = pd.read_csv("bee_mapped_ingredients.csv")
    return df, mapping

big_df, bee_mapping = load_data()

# ─────────────────────────────────────────────
# ✅ 3. 구글 시트 연결
# ─────────────────────────────────────────────
def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key("1Ek70o-JPdOJ0EF7J3JxmUwca2ZaU9ZtSkODNTN_s1h4")
    return spreadsheet.worksheet("사용자 피드백")

def save_feedback_to_gsheet(product_name, ingredient):
    sheet = get_sheet()
    name = st.session_state.get("username", "익명 사용자")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.append_row([product_name, ingredient, name, timestamp])

# ─────────────────────────────────────────────
# ✅ 4. UI 구성 + 분석 및 출력
# ─────────────────────────────────────────────
st.title("🐝 장바구니 속 숨은 꿀벌 찾기")
st.write("""전 세계 식량의 90%를 차지하는 100대 농작물 중  
70% 이상이 꿀벌의 수분 활동 덕분에 자란대요.🐝""")

st.sidebar.title("🔍 제품 검색")

product_options = [""] + sorted(big_df["PRDLST_NM"].dropna().astype(str).unique())
product_selected = st.sidebar.selectbox("제품명을 골라 주세요!", product_options)

if product_selected:
    row = big_df[big_df["PRDLST_NM"] == product_selected]

    if row.empty:
        st.warning("선택한 제품 정보를 찾을 수 없어요.")
    else:
        raw_list = [normalize(x) for x in str(row.iloc[0]["RAWMTRL_NM"]).split(",") if x.strip()]
        raw_map = {normalize(x): x.strip() for x in str(row.iloc[0]["RAWMTRL_NM"]).split(",") if x.strip()}

        related = bee_mapping[bee_mapping["원재료"].isin(raw_list)]
        related["원재료_원문"] = related["원재료"].map(raw_map)

        related_rows = related[related["꿀벌 연관 여부"] == "꿀벌 수분 연관"]
        bee_dependent_raws = related_rows["원재료_원문"].tolist()
        bee_mapped_pairs = [
            f"{row['원재료_원문']} ({row['매핑된_작물']})" 
            for _, row in related_rows.iterrows()
        ]
        score = len(bee_dependent_raws)

        if score > 0:
            st.markdown(f"""
📦 **내가 고른 제품**: {product_selected}  
🌿 **꿀벌이 없으면 안 되는 재료는?**  
{', '.join(bee_mapped_pairs)}  
🐝 **꿀벌 점수는?** → {score}점 {'🐝' * score}
""")
        else:
            st.markdown(f"""
📦 **내가 고른 제품**: {product_selected}  
🧐 꿀벌이 꼭 필요했던 재료는 아직 발견되지 않았어요.  
다른 제품에는 꿀벌의 흔적이 있을지도 몰라요! 다시 찾아볼까요?
""")

        uncertain_rows = related[related["꿀벌 연관 여부"] == "미분류"]
        if not uncertain_rows.empty:
            st.markdown("---")
            st.subheader("🧐 혹시... 이 재료도 꿀벌이 도왔을까요?")
            st.caption("AI는 이 재료들이 꿀벌과 관련 없다고 판단했지만, 틀렸을 수도 있어요! 잘못된 게 있다면 알려주세요! ✅")

            for _, row in uncertain_rows.iterrows():
                ingredient = row["원재료_원문"]
                st.markdown(f"- **{ingredient}**")

                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button(f"🐝 꿀벌 수분이 필수인 재료로 신고하기", key=f"{ingredient}_yes"):
                        save_feedback_to_gsheet(product_selected, ingredient)
                        st.success("의견이 저장되었어요! 고마워요 😊")
                with col2:
                    st.button("❌ 잘 모르겠어요", key=f"{ingredient}_no")

    st.divider()
    st.caption("🐝꿀벌은 우리가 매일 만나는 음식 뒤에 있는 특별한 친구예요. 우리 함께 꿀벌을 지켜요!🐝")
