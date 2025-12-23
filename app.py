import streamlit as st
import pdfplumber
import re
import google.generativeai as genai

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Vestibular AI", page_icon="🎓", layout="wide")

# --- FUNÇÕES DE LÓGICA ---

def extract_questions_from_pdf(pdf_file):
    full_text = ""
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    full_text += extracted + "\n"
    except Exception as e:
        return None

    # Regex poderoso para pegar "1.", "1 -", "QUESTÃO 01", etc.
    pattern = r'(?:\n|^)(?:QUESTÃO\s+)?(\d+)[\.\-\s]+'
    
    parts = re.split(pattern, full_text)
    questions = {}
    
    if len(parts) > 1:
        # Pula o índice 0 (texto antes da primeira questão) e pega pares (numero, texto)
        for i in range(1, len(parts), 2):
            q_num = parts[i]
            if i + 1 < len(parts):
                questions[q_num] = parts[i+1].strip()
            
    return questions

def parse_gabarito(gabarito_text):
    answers = {}
    # Pega "1A", "1.A", "1-A", "1 A"
    pattern = r'(\d+)[\.\-\s]+([A-Ea-e])'
    matches = re.findall(pattern, gabarito_text)
    for num, letter in matches:
        answers[num] = letter.upper()
    return answers

def ask_gemini(api_key, question, answer):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    Atue como um professor de cursinho de excelência.
    Questão: {question}
    Gabarito Oficial: {answer if answer else "Não informado"}
    
    Explique a resolução passo a passo de forma didática. 
    Se o gabarito foi fornecido, explique por que ele está certo.
    """
    response = model.generate_content(prompt)
    return response.text

# --- INTERFACE ---

st.title("🎓 Vestibular Tutor AI")
st.markdown("Seu ambiente de simulados potencializado pelo Gemini.")

with st.sidebar:
    st.header("Configuração")
    api_key = st.text_input("Gemini API Key", type="password", help="Pegue no aistudio.google.com")
    st.info("A chave não é salva, apenas usada na sessão.")

col1, col2 = st.columns(2)
with col1:
    pdf_file = st.file_uploader("Arquivo da Prova (PDF)", type="pdf")
with col2:
    gabarito_txt = st.text_area("Gabarito (Cole o texto)", height=100, placeholder="Ex: 1.A 2.B 3.C")

if pdf_file:
    questions = extract_questions_from_pdf(pdf_file)
    
    if not questions:
        st.error("Erro ao ler PDF. O arquivo deve ter texto selecionável (OCR).")
    else:
        answers = parse_gabarito(gabarito_txt) if gabarito_txt else {}
        
        # Controle de estado (qual questão está aparecendo)
        if 'q_index' not in st.session_state:
            st.session_state.q_index = 0
            
        q_keys = list(questions.keys())
        current_q_num = q_keys[st.session_state.q_index]
        current_text = questions[current_q_num]
        
        st.divider()
        st.subheader(f"Questão {current_q_num}")
        st.info(current_text)
        
        # Botoes de Ação
        c1, c2 = st.columns(2)
        with c1:
            with st.expander("Ver Resposta"):
                if current_q_num in answers:
                    st.success(f"Gabarito: **{answers[current_q_num]}**")
                else:
                    st.warning("Sem gabarito para esta questão.")
        
        with c2:
            if st.button("🤖 Explicar com IA"):
                if not api_key:
                    st.error("Precisa da API Key na barra lateral!")
                else:
                    with st.spinner("Professor Gemini analisando..."):
                        expl = ask_gemini(api_key, current_text, answers.get(current_q_num))
                        st.markdown(expl)

        st.divider()
        
        # Navegação
        col_prev, col_mid, col_next = st.columns([1, 2, 1])
        if col_prev.button("⬅️ Anterior") and st.session_state.q_index > 0:
            st.session_state.q_index -= 1
            st.rerun()
            
        col_mid.caption(f"Questão {st.session_state.q_index + 1} de {len(questions)}")
        
        if col_next.button("Próxima ➡️") and st.session_state.q_index < len(q_keys) - 1:
            st.session_state.q_index += 1
            st.rerun()