import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
from datetime import datetime, timedelta
import sqlite3
import calendar
from dateutil.relativedelta import relativedelta
import os

# Constants
DATABASE_FILE = 'finance.db'
DEFAULT_CATEGORIES = {
    'Income': ['Salary', 'Freelance', 'Investments', 'Gifts', 'Other'],
    'Expense': ['Housing', 'Food', 'Transport', 'Entertainment', 'Healthcare', 'Education', 'Shopping', 'Other']
}

# Initialize database
def init_db():
    with sqlite3.connect(DATABASE_FILE) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS transactions
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                     type TEXT, 
                     category TEXT, 
                     amount REAL, 
                     date DATE,
                     description TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS budgets
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     category TEXT,
                     amount REAL,
                     month TEXT)''')
        conn.commit()

# Initialize session state
def init_session_state():
    if 'transactions_added' not in st.session_state:
        st.session_state.transactions_added = 0
    if 'current_month' not in st.session_state:
        st.session_state.current_month = datetime.now().strftime('%Y-%m')

# Helper functions
def add_transaction(tr_type, category, amount, date, description=""):
    with sqlite3.connect(DATABASE_FILE) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO transactions (type, category, amount, date, description) VALUES (?, ?, ?, ?, ?)",
                 (tr_type, category, amount, date, description))
        conn.commit()
        st.session_state.transactions_added += 1

def get_transactions(start_date=None, end_date=None, category=None, tr_type=None):
    query = "SELECT * FROM transactions WHERE 1=1"
    params = []
    
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    if category and category != "All":
        query += " AND category = ?"
        params.append(category)
    if tr_type and tr_type != "All":
        query += " AND type = ?"
        params.append(tr_type)
        
    query += " ORDER BY date DESC"
    
    with sqlite3.connect(DATABASE_FILE) as conn:
        df = pd.read_sql(query, conn, params=params)
    
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
        df['month'] = df['date'].dt.strftime('%Y-%m')
    return df

def set_budget(category, amount, month):
    with sqlite3.connect(DATABASE_FILE) as conn:
        c = conn.cursor()
        # Check if budget exists for this category and month
        c.execute("SELECT id FROM budgets WHERE category = ? AND month = ?", (category, month))
        existing = c.fetchone()
        
        if existing:
            c.execute("UPDATE budgets SET amount = ? WHERE id = ?", (amount, existing[0]))
        else:
            c.execute("INSERT INTO budgets (category, amount, month) VALUES (?, ?, ?)",
                     (category, amount, month))
        conn.commit()

def get_budgets(month):
    with sqlite3.connect(DATABASE_FILE) as conn:
        df = pd.read_sql("SELECT category, amount FROM budgets WHERE month = ?", 
                        conn, params=(month,))
    return df

def delete_transaction(transaction_id):
    with sqlite3.connect(DATABASE_FILE) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
        conn.commit()

# Initialize app
init_db()
init_session_state()

# Page config
st.set_page_config(
    page_title="Personal Finance Tracker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main {background-color: #f8f9fa;}
    .sidebar .sidebar-content {background-color: #e9ecef;}
    .stButton>button {border-radius: 5px; border: 1px solid #ced4da;}
    .stTextInput>div>div>input, .stNumberInput>div>div>input {border-radius: 5px;}
    .stDateInput>div>div>input {border-radius: 5px;}
    .stSelectbox>div>div>select {border-radius: 5px;}
    .stRadio>div {flex-direction: row; gap: 1rem;}
    .stAlert {border-radius: 5px;}
    </style>
    """, unsafe_allow_html=True)

# Sidebar navigation
st.sidebar.title("💰 Personal Finance Tracker")
st.sidebar.markdown(f"**Current Month:** {st.session_state.current_month}")
page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Add Transaction", "Transaction History", "Budget Management", "Reports"],
    label_visibility="collapsed"
)

# Dashboard Page
if page == "Dashboard":
    st.title("📊 Financial Dashboard")
    
    # Date range selection
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", 
                                 datetime.now() - timedelta(days=30),
                                 key="dashboard_start")
    with col2:
        end_date = st.date_input("End Date", 
                               datetime.now(),
                               key="dashboard_end")
    
    # Get transactions for the selected period
    transactions = get_transactions(start_date.strftime('%Y-%m-%d'), 
                                   end_date.strftime('%Y-%m-%d'))
    
    if not transactions.empty:
        # Summary cards
        income = transactions[transactions['type'] == 'Income']['amount'].sum()
        expenses = transactions[transactions['type'] == 'Expense']['amount'].sum()
        balance = income - expenses
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Income", f"${income:,.2f}")
        col2.metric("Total Expenses", f"${expenses:,.2f}")
        col3.metric("Balance", f"${balance:,.2f}", delta_color="inverse")
        
        # Monthly trends
        st.subheader("Monthly Trends")
        monthly_data = transactions.groupby(['month', 'type'])['amount'].sum().unstack().fillna(0)
        monthly_data['Balance'] = monthly_data.get('Income', 0) - monthly_data.get('Expense', 0)
        
        fig = px.line(monthly_data, 
                     x=monthly_data.index, 
                     y=['Income', 'Expense', 'Balance'],
                     markers=True,
                     title="Monthly Income vs Expenses")
        st.plotly_chart(fig, use_container_width=True)
        
        # Expense breakdown
        st.subheader("Expense Breakdown")
        expense_data = transactions[transactions['type'] == 'Expense']
        if not expense_data.empty:
            col1, col2 = st.columns(2)
            with col1:
                category_sum = expense_data.groupby('category')['amount'].sum().sort_values()
                fig1 = px.bar(category_sum, 
                             x=category_sum.values, 
                             y=category_sum.index,
                             orientation='h',
                             title="Expenses by Category")
                st.plotly_chart(fig1, use_container_width=True)
            
            with col2:
                fig2 = px.pie(expense_data, 
                              values='amount', 
                              names='category',
                              title="Expense Distribution")
                st.plotly_chart(fig2, use_container_width=True)
    else:
        st.warning("No transactions found for the selected period.")

# Add Transaction Page
elif page == "Add Transaction":
    st.title("➕ Add Transaction")
    
    with st.form("transaction_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            tr_type = st.radio("Transaction Type", 
                              ["Income", "Expense"],
                              horizontal=True)
        with col2:
            category = st.selectbox("Category", 
                                  DEFAULT_CATEGORIES[tr_type])
        
        amount = st.number_input("Amount ($)", 
                               min_value=0.01, 
                               step=0.01,
                               format="%.2f")
        
        date = st.date_input("Date", 
                           datetime.now())
        
        description = st.text_input("Description (Optional)")
        
        submitted = st.form_submit_button("Add Transaction")
        if submitted:
            if amount <= 0:
                st.error("Amount must be greater than 0")
            else:
                add_transaction(tr_type, category, amount, date, description)
                st.success("Transaction added successfully!")
                st.balloons()

# Transaction History Page
elif page == "Transaction History":
    st.title("📜 Transaction History")
    
    # Filters
    with st.expander("🔍 Filters", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            start_date = st.date_input("From Date", 
                                      datetime.now() - timedelta(days=30))
        with col2:
            end_date = st.date_input("To Date", 
                                   datetime.now())
        with col3:
            tr_type = st.selectbox("Transaction Type", 
                                 ["All", "Income", "Expense"])
    
    # Category filter
    categories = ["All"] + DEFAULT_CATEGORIES['Income'] + DEFAULT_CATEGORIES['Expense']
    selected_category = st.selectbox("Category", categories)
    
    # Get filtered transactions
    transactions = get_transactions(
        start_date.strftime('%Y-%m-%d'),
        end_date.strftime('%Y-%m-%d'),
        None if selected_category == "All" else selected_category,
        None if tr_type == "All" else tr_type
    )
    
    if not transactions.empty:
        # Display transactions
        st.dataframe(
            transactions[['date', 'type', 'category', 'amount', 'description']],
            column_config={
                "date": "Date",
                "type": "Type",
                "category": "Category",
                "amount": st.column_config.NumberColumn(
                    "Amount",
                    format="$%.2f"
                ),
                "description": "Description"
            },
            hide_index=True,
            use_container_width=True
        )
        
        # Download button
        csv = transactions.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Export as CSV",
            csv,
            "transactions.csv",
            "text/csv",
            key='download-csv'
        )
    else:
        st.info("No transactions found matching your filters.")

# Budget Management Page
elif page == "Budget Management":
    st.title("💰 Budget Management")
    
    # Month selection
    months = [(datetime.now() + relativedelta(months=i)).strftime('%Y-%m') 
              for i in range(-3, 4)]
    selected_month = st.selectbox("Select Month", months, index=3)
    
    # Current budgets
    st.subheader("Current Budgets")
    budgets = get_budgets(selected_month)
    
    if not budgets.empty:
        st.dataframe(
            budgets,
            column_config={
                "category": "Category",
                "amount": st.column_config.NumberColumn(
                    "Amount",
                    format="$%.2f"
                )
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("No budgets set for this month.")
    
    # Set new budget
    st.subheader("Set Budget")
    with st.form("budget_form"):
        col1, col2 = st.columns(2)
        with col1:
            category = st.selectbox("Category", 
                                  DEFAULT_CATEGORIES['Expense'])
        with col2:
            amount = st.number_input("Amount ($)", 
                                   min_value=0.01, 
                                   step=0.01,
                                   format="%.2f")
        
        submitted = st.form_submit_button("Save Budget")
        if submitted:
            set_budget(category, amount, selected_month)
            st.success("Budget saved successfully!")
            st.experimental_rerun()

# Reports Page
elif page == "Reports":
    st.title("📈 Financial Reports")
    
    # Month selection
    months = [(datetime.now() + relativedelta(months=i)).strftime('%Y-%m') 
              for i in range(-12, 1)]
    selected_month = st.selectbox("Select Month for Report", months, index=len(months)-1)
    
    # Get data for the selected month
    # In the Reports section (around line 356):
    first_day = datetime.strptime(selected_month, '%Y-%m').date()
    last_day = (first_day + relativedelta(months=1)) - timedelta(days=1)  # Fixed line
    
    transactions = get_transactions(first_day.strftime('%Y-%m-%d'), 
                                  last_day.strftime('%Y-%m-%d'))
    budgets = get_budgets(selected_month)
    
    if not transactions.empty:
        # Monthly summary
        income = transactions[transactions['type'] == 'Income']['amount'].sum()
        expenses = transactions[transactions['type'] == 'Expense']['amount'].sum()
        balance = income - expenses
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Income", f"${income:,.2f}")
        col2.metric("Total Expenses", f"${expenses:,.2f}")
        col3.metric("Balance", f"${balance:,.2f}", delta_color="inverse")
        
        # Budget vs Actual
        if not budgets.empty:
            st.subheader("Budget vs Actual Spending")
            expense_data = transactions[transactions['type'] == 'Expense']
            budget_comparison = budgets.merge(
                expense_data.groupby('category')['amount'].sum().reset_index(),
                on='category',
                how='left'
            ).fillna(0)
            budget_comparison['difference'] = budget_comparison['amount_x'] - budget_comparison['amount_y']
            budget_comparison['percentage'] = (budget_comparison['amount_y'] / budget_comparison['amount_x']) * 100
            
            st.dataframe(
                budget_comparison.rename(columns={
                    'category': 'Category',
                    'amount_x': 'Budget',
                    'amount_y': 'Actual',
                    'difference': 'Remaining',
                    'percentage': 'Used (%)'
                }),
                column_config={
                    "Budget": st.column_config.NumberColumn(format="$%.2f"),
                    "Actual": st.column_config.NumberColumn(format="$%.2f"),
                    "Remaining": st.column_config.NumberColumn(format="$%.2f"),
                    "Used (%)": st.column_config.NumberColumn(format="%.1f%%")
                },
                hide_index=True,
                use_container_width=True
            )
        
        # Daily spending
        st.subheader("Daily Spending")
        daily_spending = transactions[transactions['type'] == 'Expense']
        if not daily_spending.empty:
            daily_spending = daily_spending.groupby('date')['amount'].sum().reset_index()
            fig = px.line(daily_spending, 
                         x='date', 
                         y='amount',
                         markers=True,
                         title="Daily Expenses")
            st.plotly_chart(fig, use_container_width=True)
        
        # Category breakdown
        st.subheader("Category Breakdown")
        col1, col2 = st.columns(2)
        with col1:
            income_data = transactions[transactions['type'] == 'Income']
            if not income_data.empty:
                fig1 = px.pie(income_data, 
                              values='amount', 
                              names='category',
                              title="Income Sources")
                st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            expense_data = transactions[transactions['type'] == 'Expense']
            if not expense_data.empty:
                fig2 = px.pie(expense_data, 
                              values='amount', 
                              names='category',
                              title="Expense Categories")
                st.plotly_chart(fig2, use_container_width=True)
    else:
        st.warning("No transactions found for the selected month.")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("""
**Tips:**
- Add transactions regularly
- Review your budget monthly
- Export data for backup
""")

# Run with: streamlit run finance_app.py