import streamlit as st
import pdfplumber
import re
import google.generativeai as genai

# --- 1. CONFIGURAÇÃO VISUAL E CSS ---
st.set_page_config(page_title="Vestibular Master", page_icon="🎓", layout="centered")

# CSS para limpar a interface e melhorar a tipografia
st.markdown("""
    <style>
    .stApp {
        background-color: #f8f9fa;
    }
    .question-card {
        background-color: #ffffff;
        padding: 30px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border: 1px solid #e0e0e0;
        font-size: 18px;
        line-height: 1.6;
        color: #2c3e50;
        margin-bottom: 20px;
    }
    .stButton button {
        width: 100%;
        border-radius: 8px;
        height: 50px;
    }
    .header-text {
        color: #1e3a8a;
        font-weight: 700;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. FUNÇÕES DE EXTRAÇÃO (LÓGICA) ---

def extract_text_two_columns(page):
    """Lê coluna esquerda depois coluna direita (para provas tipo Univesp)."""
    width, height = page.width, page.height
    
    # Margens de corte (ajuste se cortar cabeçalho/rodapé)
    top_crop = height * 0.10
    bottom_crop = height * 0.90
    
    left_box = (0, top_crop, width/2, bottom_crop)
    right_box = (width/2, top_crop, width, bottom_crop)
    
    text_left = page.crop(left_box).extract_text() or ""
    text_right = page.crop(right_box).extract_text() or ""
    
    return text_left + "\n" + text_right

def extract_questions_pdf(pdf_file):
    """Extrai texto e separa por 'QUESTÃO XX'."""
    full_text = ""
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                full_text += extract_text_two_columns(page)
    except Exception as e:
        return None

    # Limpeza básica
    cleanup = ["Confidencial até o momento da aplicação", "UVSP2404", "Rascunho"]
    for junk in cleanup:
        full_text = full_text.replace(junk, "")

    # Regex para quebrar nas questões
    pattern = r'(?:QUESTÃO\s+)(\d+)'
    parts = re.split(pattern, full_text)
    
    questions = {}
    if len(parts) > 1:
        for i in range(1, len(parts), 2):
            q_num = str(int(parts[i])) # Remove zeros à esquerda (01 -> 1)
            if i + 1 < len(parts):
                questions[q_num] = parts[i+1].strip()
    return questions

def extract_gabarito_pdf(pdf_file):
    """
    Lê o PDF do gabarito e extrai pares Número-Letra.
    Suporta formatos sujos como: $1-E$, 28C, 15\div D
    """
    text = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
            
    answers = {}
    # Regex Explicado:
    # (\d{1,2})  -> Captura 1 ou 2 dígitos (ex: 1, 56)
    # [\W_]* -> Ignora qualquer símbolo (hífen, cifrão, espaço, barra)
    # ([A-E])    -> Captura a letra da resposta
    matches = re.findall(r'(\d{1,2})[\W_]*([A-E])', text, re.IGNORECASE)
    
    for num, letter in matches:
        answers[str(int(num))] = letter.upper()
        
    return answers

def ask_gemini(api_key, question_text, correct_answer):
    if not api_key:
        return "🔒 Insira sua API Key na barra lateral para ver a explicação."
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Aja como um professor particular de vestibular.
        Questão: {question_text}
        Gabarito Oficial: {correct_answer}
        
        Explique de forma didática e objetiva como chegar na resposta correta.
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Erro de conexão com IA: {e}"

# --- 3. INTERFACE (FRONTEND) ---

# Sidebar para Uploads
with st.sidebar:
    st.markdown("### ⚙️ Configurações")
    api_key = st.text_input("Gemini API Key", type="password")
    
    st.markdown("---")
    st.markdown("### 📂 Arquivos")
    pdf_prova = st.file_uploader("1. Caderno de Questões (PDF)", type="pdf")
    pdf_gabarito = st.file_uploader("2. Gabarito (PDF)", type="pdf")
    
    st.info("O sistema ajusta automaticamente as colunas da prova da Univesp.")

# Área Principal
if pdf_prova:
    # Processamento
    questions = extract_questions_pdf(pdf_prova)
    
    # Processamento do Gabarito (se houver)
    answers = {}
    if pdf_gabarito:
        answers = extract_gabarito_pdf(pdf_gabarito)

    if not questions:
        st.error("Erro na leitura. Verifique se o PDF é legível (OCR).")
    else:
        # Estado da navegação
        if 'q_idx' not in st.session_state:
            st.session_state.q_idx = 0
            
        q_keys = sorted(questions.keys(), key=lambda x: int(x))
        total_q = len(q_keys)
        
        # Garante índice válido
        if st.session_state.q_idx >= total_q:
            st.session_state.q_idx = 0
            
        current_num = q_keys[st.session_state.q_idx]
        current_txt = questions[current_num]
        current_ans = answers.get(current_num, None)

        # --- CABEÇALHO DA QUESTÃO ---
        # Barra de progresso
        progress = (st.session_state.q_idx + 1) / total_q
        st.progress(progress)
        
        col_title, col_status = st.columns([3, 1])
        with col_title:
            st.markdown(f"<h2 class='header-text'>Questão {current_num}</h2>", unsafe_allow_html=True)
        with col_status:
            st.caption(f"{st.session_state.q_idx + 1}/{total_q}")

        # --- CARD DA QUESTÃO (VISUAL LIMPO) ---
        st.markdown(f"""
            <div class="question-card">
                {current_txt}
            </div>
        """, unsafe_allow_html=True)

        # --- ÁREA DE RESPOSTA E IA ---
        st.markdown("### 📝 Resolução")
        
        col_gab, col_ai = st.columns(2)
        
        with col_gab:
            # Container estilizado para o gabarito
            with st.container(border=True):
                st.markdown("**Gabarito Oficial**")
                if st.button("👁️ Revelar Resposta", key=f"btn_rev_{current_num}"):
                    if current_ans:
                        st.success(f"A alternativa correta é: **{current_ans}**")
                    else:
                        st.warning("Gabarito não encontrado para esta questão.")
                        
        with col_ai:
            with st.container(border=True):
                st.markdown("**Professor IA**")
                if st.button("🤖 Explicar Passo a Passo", key=f"btn_ai_{current_num}"):
                    with st.spinner("Gerando explicação..."):
                        expl = ask_gemini(api_key, current_txt, current_ans)
                        st.markdown(expl)

        st.markdown("---")

        # --- RODAPÉ DE NAVEGAÇÃO ---
        c1, c2, c3 = st.columns([1, 2, 1])
        
        if c1.button("⬅️ Anterior"):
            if st.session_state.q_idx > 0:
                st.session_state.q_idx -= 1
                st.rerun()
                
        if c3.button("Próxima ➡️"):
            if st.session_state.q_idx < total_q - 1:
                st.session_state.q_idx += 1
                st.rerun()

else:
    # TELA INICIAL (QUANDO NÃO TEM ARQUIVO)
    st.markdown("""
    <div style="text-align: center; padding: 50px;">
        <h1>🎓 Bem-vindo ao Vestibular Master</h1>
        <p style="font-size: 18px;">Faça upload do caderno de prova e do gabarito na barra lateral para começar seus estudos.</p>
    </div>
    """, unsafe_allow_html=True)