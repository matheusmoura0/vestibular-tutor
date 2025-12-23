import streamlit as st
import pdfplumber
import re
import google.generativeai as genai

# --- 1. CONFIGURAÇÃO E CSS ---
st.set_page_config(page_title="Vestibular Simulator", page_icon="✍️", layout="centered")

st.markdown("""
    <style>
    /* Estilo Geral */
    .stApp { background-color: #f0f2f6; }
    
    /* Card da Questão */
    .question-card {
        background-color: white;
        padding: 30px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        border-left: 6px solid #3b82f6; /* Detalhe azul na esquerda */
        margin-bottom: 20px;
        font-size: 18px;
        color: #1f2937;
    }
    
    /* Numeração da Questão */
    .q-number {
        color: #3b82f6;
        font-weight: 800;
        font-size: 1.2rem;
        text-transform: uppercase;
        margin-bottom: 10px;
        display: block;
    }

    /* Botões de Alternativa Customizados */
    div.stButton > button {
        width: 100%;
        height: 60px;
        border-radius: 10px;
        font-weight: bold;
        font-size: 20px;
        transition: all 0.2s;
    }
    
    /* Destaque para mensagem de erro/acerto */
    .feedback-box {
        padding: 15px;
        border-radius: 8px;
        margin-top: 10px;
        text-align: center;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. FUNÇÕES DE EXTRAÇÃO (MANTIDAS) ---

def extract_text_two_columns(page):
    width, height = page.width, page.height
    top_crop = height * 0.10
    bottom_crop = height * 0.90
    left_box = (0, top_crop, width/2, bottom_crop)
    right_box = (width/2, top_crop, width, bottom_crop)
    text_left = page.crop(left_box).extract_text() or ""
    text_right = page.crop(right_box).extract_text() or ""
    return text_left + "\n" + text_right

def extract_questions_pdf(pdf_file):
    full_text = ""
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                full_text += extract_text_two_columns(page)
    except Exception:
        return None

    cleanup = ["Confidencial até o momento da aplicação", "UVSP2404", "Rascunho"]
    for junk in cleanup:
        full_text = full_text.replace(junk, "")

    pattern = r'(?:QUESTÃO\s+)(\d+)'
    parts = re.split(pattern, full_text)
    questions = {}
    if len(parts) > 1:
        for i in range(1, len(parts), 2):
            q_num = str(int(parts[i])) 
            if i + 1 < len(parts):
                questions[q_num] = parts[i+1].strip()
    return questions

def extract_gabarito_pdf(pdf_file):
    text = ""
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
        answers = {}
        matches = re.findall(r'(\d{1,2})[\W_]*([A-E])', text, re.IGNORECASE)
        for num, letter in matches:
            answers[str(int(num))] = letter.upper()
        return answers
    except:
        return {}

def ask_gemini(api_key, question_text, correct_answer):
    if not api_key:
        return "⚠️ Configure a API Key na barra lateral."
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Você é um tutor de vestibular. O aluno tentou responder a questão.
        Questão: {question_text}
        Gabarito Correto: {correct_answer}
        
        Explique por que essa é a correta e analise brevemente por que as outras estariam erradas se possível.
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Erro: {e}"

# --- 3. ESTADO DA SESSÃO (INIT) ---
if 'user_answers' not in st.session_state:
    st.session_state.user_answers = {} # Dicionário: {'1': 'A', '5': 'C'}

if 'q_idx' not in st.session_state:
    st.session_state.q_idx = 0

# --- 4. INTERFACE ---

with st.sidebar:
    st.header("⚙️ Painel de Controle")
    api_key = st.text_input("Gemini API Key", type="password")
    st.markdown("---")
    pdf_prova = st.file_uploader("1. Prova (PDF)", type="pdf")
    pdf_gabarito = st.file_uploader("2. Gabarito (PDF)", type="pdf")
    
    # Resetar progresso
    if st.button("🗑️ Limpar Respostas"):
        st.session_state.user_answers = {}
        st.rerun()

if pdf_prova:
    questions = extract_questions_pdf(pdf_prova)
    answers = extract_gabarito_pdf(pdf_gabarito) if pdf_gabarito else {}
    
    if not questions:
        st.error("Não foi possível ler as questões.")
    else:
        q_keys = sorted(questions.keys(), key=lambda x: int(x))
        total_q = len(q_keys)
        
        # Garante índice válido
        if st.session_state.q_idx >= total_q: st.session_state.q_idx = 0
        if st.session_state.q_idx < 0: st.session_state.q_idx = 0
            
        current_num = q_keys[st.session_state.q_idx]
        current_txt = questions[current_num]
        official_ans = answers.get(current_num, None)
        
        # Recupera resposta do usuário se já existir
        user_choice = st.session_state.user_answers.get(current_num, None)

        # Barra de Progresso Superior
        st.progress((st.session_state.q_idx + 1) / total_q)
        
        # --- EXIBIÇÃO DA QUESTÃO ---
        st.markdown(f"""
            <div class="question-card">
                <span class="q-number">QUESTÃO {current_num}</span>
                {current_txt}
            </div>
        """, unsafe_allow_html=True)

        # --- ÁREA DE INTERAÇÃO (BOTÕES) ---
        st.markdown("### Escolha a alternativa:")
        
        # Colunas para os botões A, B, C, D, E
        cols = st.columns(5)
        options = ['A', 'B', 'C', 'D', 'E']
        
        # Renderiza os botões
        for idx, opt in enumerate(options):
            # Se o usuário clicar, salvamos no estado
            if cols[idx].button(opt, key=f"btn_{current_num}_{opt}", 
                                type="primary" if user_choice == opt else "secondary"):
                st.session_state.user_answers[current_num] = opt
                st.rerun() # Recarrega para processar o feedback

        # --- FEEDBACK E IA ---
        if user_choice:
            st.markdown("---")
            
            # Verificação de Acerto/Erro
            if not official_ans:
                st.warning(f"Você escolheu **{user_choice}**, mas não carregou o gabarito ainda.")
            elif user_choice == official_ans:
                st.success(f"✅ **Parabéns!** A alternativa **{user_choice}** está correta.")
            else:
                st.error(f"❌ **Ops!** Você marcou **{user_choice}**, mas a correta é **{official_ans}**.")
            
            # Botão de Explicação (Só aparece se já respondeu)
            if st.button("🤖 Por que essa é a resposta?"):
                with st.spinner("Professor Gemini explicando..."):
                    expl = ask_gemini(api_key, current_txt, official_ans)
                    st.markdown(expl)

        st.markdown("<br>", unsafe_allow_html=True)
        
        # --- NAVEGAÇÃO ---
        c1, c2, c3 = st.columns([1, 2, 1])
        if c1.button("⬅️ Anterior"):
            st.session_state.q_idx -= 1
            st.rerun()
            
        if c3.button("Próxima ➡️"):
            st.session_state.q_idx += 1
            st.rerun()

else:
    st.info("👆 Faça o upload dos arquivos para começar o simulado.")