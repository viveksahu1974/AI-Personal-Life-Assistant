import React, { useCallback, useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  Activity, ArrowDownRight, ArrowRight, ArrowUpRight, Bell, CalendarDays,
  Check, CheckCheck, CheckCircle2, ChevronRight, Circle, Clock3, CreditCard,
  DollarSign, Edit3, GraduationCap, Heart, LayoutDashboard, Menu, MessageCircle,
  MoreHorizontal, Plus, Search, Send, Settings2, ShieldCheck, Sparkles,
  Target, Trash2, Wallet, X, Zap, AlertTriangle, Play, RefreshCw, CalendarClock, Download, Undo2, TrendingUp, TrendingDown, Filter, FileSpreadsheet, FileText, ReceiptText, BarChart3,
} from 'lucide-react'
import { api, downloadExpenseReport, monthLocal, todayLocal, niceDate, rupees, toIso, toLocalInput } from './api'
import './style.css'

const nav = [
  { key: 'overview', label: 'Overview', icon: LayoutDashboard },
  { key: 'tasks', label: 'My Tasks', icon: CheckCircle2 },
  { key: 'reminders', label: 'Reminders', icon: Bell },
  { key: 'expenses', label: 'Expenses', icon: Wallet },
  { key: 'assistant', label: 'AI Assistant', icon: Sparkles },
]
const categoryIcons = { Personal: Heart, College: GraduationCap, Work: Target, Health: Activity }
const defaultTask = { title: '', notes: '', priority: 'Medium', category: 'Personal', due_at: '' }
const emptyReminder = { title: '', message: '', remind_at: '' }
const expenseCategories = ['Food','Study','Travel','Shopping','Bank','House Rent','Personal','Gym','Health','Drink','Petrol','Clothes','Other','Bills','Education']
const emptyExpense = () => ({ title: '', amount: '', category: 'Food', entry_type: 'debit', notes: '', spent_on: todayLocal() })

function Pill({ children, className = '' }) { return <span className={`pill ${className}`}>{children}</span> }
function Empty({ icon: Icon = Circle, title, text }) { return <div className="empty"><span className="empty-icon"><Icon size={24}/></span><h3>{title}</h3><p>{text}</p></div> }
function SectionHeading({ eyebrow, title, subtitle, action }) { return <div className="section-heading"><div>{eyebrow && <span className="eyebrow">{eyebrow}</span>}<h1>{title}</h1>{subtitle && <p>{subtitle}</p>}</div>{action}</div> }
function IconButton({ icon: Icon, label, ...props }) { return <button className="icon-button" aria-label={label} title={label} {...props}><Icon size={17}/></button> }

function TaskRow({ task, onToggle, onEdit, onDelete, compact = false }) {
  const Icon = categoryIcons[task.category] || Target
  const overdue = task.due_at && !task.completed && new Date(task.due_at) < new Date()
  return <div className={`task-row ${task.completed ? 'is-complete' : ''}`}>
    <button className={`task-check ${task.completed ? 'checked' : ''}`} onClick={() => onToggle(task)} title={task.completed ? 'Mark as active' : 'Mark complete'} aria-label="Toggle task">
      {task.completed && <Check size={14} strokeWidth={3}/>}</button>
    <div className="task-content"><div className="task-main"><strong>{task.title}</strong>{task.priority === 'High' && !task.completed && <Pill className="priority-high">High priority</Pill>}</div>
      <div className="task-meta"><span><Icon size={13}/>{task.category}</span><span className={overdue ? 'overdue' : ''}><Clock3 size={13}/>{task.due_at ? niceDate(task.due_at) : 'Anytime'}</span></div>
      {!compact && task.notes && <p className="task-notes">{task.notes}</p>}
    </div>
    {!compact && <div className="task-actions"><IconButton icon={Edit3} label="Edit task" onClick={() => onEdit(task)}/><IconButton icon={Trash2} label="Delete task" onClick={() => onDelete(task)}/></div>}
  </div>
}

function Sidebar({ tab, setTab, mobile, closeMobile, dueCount }) {
  return <><div className={`mobile-overlay ${mobile ? 'show' : ''}`} onClick={closeMobile}/><aside className={`sidebar ${mobile ? 'sidebar-open' : ''}`}>
    <div className="brand"><span className="brand-symbol"><Sparkles size={23} fill="currentColor" strokeWidth={1.5}/></span><div><strong>LifePilot</strong><small>YOUR PERSONAL SPACE</small></div><button className="mobile-close" onClick={closeMobile} aria-label="Close menu"><X size={20}/></button></div>
    <div className="workspace-label">WORKSPACE</div>
    <nav className="nav-list">{nav.map(item => <button key={item.key} className={`nav-item ${tab === item.key ? 'active' : ''}`} onClick={() => { setTab(item.key); closeMobile() }}><item.icon size={19}/><span>{item.label}</span>{item.key === 'reminders' && dueCount > 0 && <span className="nav-counter">{dueCount}</span>}</button>)}</nav>
    <div className="workspace-label tools-label">PREFERENCES</div>
    <button className={`nav-item ${tab === 'settings' ? 'active' : ''}`} onClick={() => { setTab('settings'); closeMobile() }}><Settings2 size={19}/>Settings</button>
    <div className="sidebar-bottom"><div className="sidebar-tip"><span><Zap size={16} fill="currentColor"/></span><strong>Small steps. Big progress.</strong><p>Your goals deserve a little momentum every day.</p></div><div className="sidebar-footer"><span className="avatar">L</span><span><strong>My Workspace</strong><small>Private local app</small></span><ShieldCheck size={17}/></div></div>
  </aside></>
}

function Overview({ data, onTab, onToggle, onNewTask, onAsk }) {
  if (!data) return <div className="skeleton">Loading your dashboard...</div>
  const { tasks, focus, spending, budget, categories, upcoming_reminders, recent_expenses } = data
  const progress = tasks.total ? Math.round(100 * tasks.done / tasks.total) : 0
  const budgetPercent = budget ? Math.min(100, Math.round(spending / budget * 100)) : 0
  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'
  return <>
    <div className="welcome"><div className="welcome-copy"><div className="welcome-label"><span className="online-dot"/> YOUR PERSONAL COMMAND CENTER</div><h1>{greeting}<span className="wave"> ✨</span></h1><p>A clearer day starts here. You have <strong>{tasks.active} tasks</strong> waiting for your attention. You're doing great.</p><div className="welcome-actions"><button className="button button-white" onClick={onNewTask}><Plus size={17}/> Add a task</button><button className="button button-ghost-light" onClick={onAsk}><Sparkles size={17}/> Plan my day <ArrowRight size={16}/></button></div></div><div className="welcome-art" aria-hidden="true"><div className="glow glow-one"/><div className="glow glow-two"/><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="art-planet"><Sparkles size={53}/></div><div className="art-star star-one">✦</div><div className="art-star star-two">✧</div></div></div>
    <div className="stats-grid">
      <Metric title="Active Tasks" value={tasks.active} icon={Target} tone="purple" hint="Things on your list" delta={<span className="soft-success"><ArrowUpRight size={14}/> Stay focused</span>}/>
      <Metric title="Completed" value={tasks.done} icon={CheckCheck} tone="green" hint="Tasks finished" delta={<span className="soft-success"><Check size={13}/> Nice work</span>}/>
      <Metric title="Overdue Tasks" value={tasks.overdue} icon={Clock3} tone="orange" hint="Need your attention" delta={<span className={tasks.overdue ? 'soft-warn' : 'soft-success'}>{tasks.overdue ? 'Take action' : 'All caught up'}</span>}/>
      <Metric title="Month's Expenses" value={rupees(spending)} icon={Wallet} tone="blue" hint="Your monthly spending" delta={<span className="muted-small">{budget ? `${Math.max(0, 100 - budgetPercent)}% budget left` : 'No budget set'}</span>}/>
    </div>
    <div className="main-grid"><div className="panel"><div className="panel-heading"><div><h2>Today's focus</h2><p>Your most important next steps</p></div><button className="text-link" onClick={() => onTab('tasks')}>View all <ArrowRight size={16}/></button></div>
      {focus.length ? <div className="focus-list">{focus.map(t => <TaskRow key={t.id} task={t} onToggle={onToggle} compact/>)}</div> : <Empty icon={CheckCircle2} title="Your day is wide open" text="Add a task to build your priority list."/>}
    </div><div className="panel progress-panel"><div className="panel-heading"><div><h2>Productivity</h2><p>Overall task completion</p></div><MoreHorizontal size={20} color="#a1a5b5"/></div><div className="ring-area"><div className="progress-ring" style={{ '--progress': `${progress}%` }}><div><strong>{progress}%</strong><span>completed</span></div></div></div><div className="progress-summary"><span><i className="dot purple"/> Completed <strong>{tasks.done}</strong></span><span><i className="dot pale"/> Remaining <strong>{tasks.active}</strong></span></div><div className="progress-note"><Zap size={16}/> Consistency makes all the difference.</div></div></div>
    <div className="main-grid lower-grid"><div className="panel"><div className="panel-heading"><div><h2>Spending snapshot</h2><p>{new Date(data.month + '-01T12:00:00').toLocaleString('en-IN', { month: 'long', year: 'numeric' })}</p></div><button className="text-link" onClick={() => onTab('expenses')}>Manage <ArrowRight size={16}/></button></div>
      <div className="money-summary"><div><span>Spent this month</span><strong>{rupees(spending)}</strong></div><div className="money-budget"><span>Monthly budget</span><strong>{budget ? rupees(budget) : 'Not set'}</strong></div></div>
      <div className="budget-track"><div style={{ width: `${budgetPercent}%`, background: budget && spending > budget ? '#ef876b' : undefined }}/></div>
      <div className="category-list">{categories.length ? categories.slice(0,4).map((c,i) => <div className="category-line" key={c.category}><span><i className={`category-dot c${i % 4}`}/>{c.category}</span><strong>{rupees(c.total)}</strong></div>) : <div className="muted-empty">No expenses recorded this month yet.</div>}</div>
    </div><div className="panel"><div className="panel-heading"><div><h2>Upcoming reminders</h2><p>Never miss a moment</p></div><button className="text-link" onClick={() => onTab('reminders')}>See all <ArrowRight size={16}/></button></div>
      {upcoming_reminders.length ? <div className="mini-reminders">{upcoming_reminders.map(r => <div className="mini-reminder" key={r.id}><span className="mini-reminder-icon"><Bell size={17}/></span><div><strong>{r.title}</strong><small>{niceDate(r.remind_at)}</small></div><ChevronRight size={17}/></div>)}</div> : <Empty icon={Bell} title="No reminders scheduled" text="Create one to stay on top of important things."/>}
    </div></div>
  </>
}
function Metric({ title, value, icon: Icon, tone, hint, delta }) { return <div className="metric"><span className={`metric-icon ${tone}`}><Icon size={21}/></span><div className="metric-top">{title}</div><div className="metric-value">{value}</div><div className="metric-bottom"><span>{hint}</span>{delta}</div></div> }

function TaskScreen({ tasks, onCreate, onUpdate, onToggle, onDelete }) {
  const [filter, setFilter] = useState('active')
  const [query, setQuery] = useState('')
  const [form, setForm] = useState(defaultTask)
  const [editing, setEditing] = useState(null)
  const [saving, setSaving] = useState(false)
  const visible = tasks.filter(t => (filter === 'all' || (filter === 'active' ? !t.completed : !!t.completed)) && `${t.title} ${t.notes}`.toLowerCase().includes(query.toLowerCase()))
  const edit = t => { setEditing(t.id); setForm({ title:t.title, notes:t.notes, priority:t.priority, category:t.category, due_at:toLocalInput(t.due_at) }); document.getElementById('task-title')?.focus() }
  const submit = async e => { e.preventDefault(); setSaving(true); try { const data={...form,due_at:toIso(form.due_at)}; if (editing) await onUpdate(editing,data); else await onCreate(data); setForm(defaultTask); setEditing(null) } finally { setSaving(false) } }
  return <><SectionHeading eyebrow="ORGANIZE YOUR DAY" title="Tasks & priorities" subtitle="Make a plan, keep moving, and celebrate every win." action={<Pill className="count-pill">{tasks.filter(t => !t.completed).length} active tasks</Pill>}/>
    <div className="work-grid"><div className="panel form-panel"><div className="panel-heading"><div><h2>{editing ? 'Edit your task' : 'Create a new task'}</h2><p>{editing ? 'Update the details below' : 'A small step toward a big goal'}</p></div><span className="form-top-icon"><Plus size={21}/></span></div>
      <form onSubmit={submit} className="form-stack"><label>Task title<input id="task-title" required maxLength={150} placeholder="e.g. Complete DAA assignment" value={form.title} onChange={e => setForm({...form,title:e.target.value})}/></label><label>Notes (optional)<textarea maxLength={1500} rows={3} placeholder="Add any useful details..." value={form.notes} onChange={e => setForm({...form,notes:e.target.value})}/></label><div className="form-pair"><label>Category<select value={form.category} onChange={e => setForm({...form,category:e.target.value})}>{['Personal','College','Work','Health'].map(c => <option key={c}>{c}</option>)}</select></label><label>Priority<select value={form.priority} onChange={e => setForm({...form,priority:e.target.value})}>{['Low','Medium','High'].map(p => <option key={p}>{p}</option>)}</select></label></div><label>Due date & time (optional)<input type="datetime-local" value={form.due_at} onChange={e => setForm({...form,due_at:e.target.value})}/></label><button disabled={saving} className="button button-primary" type="submit">{saving ? 'Saving...' : editing ? 'Save changes' : 'Add task'} <ArrowRight size={17}/></button>{editing && <button type="button" className="button button-soft" onClick={() => { setEditing(null); setForm(defaultTask) }}>Cancel editing</button>}</form>
    </div><div className="panel tasks-panel"><div className="panel-heading"><div><h2>Your task list</h2><p>Focus on what matters today</p></div></div><div className="task-toolbar"><div className="filter-tabs">{['active','all','done'].map(f => <button key={f} className={filter===f ? 'selected':''} onClick={() => setFilter(f)}>{f==='done'?'Completed':f[0].toUpperCase()+f.slice(1)}</button>)}</div><div className="search-box"><Search size={16}/><input placeholder="Search tasks" value={query} onChange={e => setQuery(e.target.value)}/></div></div>
      {visible.length ? <div className="task-full-list">{visible.map(t => <TaskRow key={t.id} task={t} onToggle={onToggle} onEdit={edit} onDelete={onDelete}/>)}</div> : <Empty icon={CheckCircle2} title="Nothing to show yet" text="Add a task or switch the filter."/>}</div></div>
  </>
}

function ReminderScreen({ reminders, onCreate, onAck, onDelete, onEnableNotify, permission }) {
  const [form,setForm]=useState(emptyReminder)
  const [saving,setSaving]=useState(false)
  const submit=async e=>{e.preventDefault();setSaving(true);try{await onCreate({...form,remind_at:toIso(form.remind_at)});setForm(emptyReminder)}finally{setSaving(false)}}
  const pending=reminders.filter(r=>!r.acknowledged_at)
  const archived=reminders.filter(r=>!!r.acknowledged_at)
  return <><SectionHeading eyebrow="DON'T MISS A THING" title="Reminders" subtitle="Be on time for everything that matters." action={<button onClick={onEnableNotify} className="button button-outline"><Bell size={16}/>{permission==='granted'?'Browser alerts enabled':'Enable browser alerts'}</button>}/>
    <div className="notice"><Bell size={19}/><span><strong>How alerts work:</strong> Browser notifications appear while this app is open and permission is granted. Missed alerts are waiting here when you return. For email alerts while the site is closed, configure SMTP in the backend.</span></div>
    <div className="work-grid"><div className="panel form-panel"><div className="panel-heading"><div><h2>Schedule a reminder</h2><p>Give yourself a gentle nudge</p></div><span className="form-top-icon"><CalendarClock size={21}/></span></div><form className="form-stack" onSubmit={submit}><label>Reminder title<input required placeholder="e.g. Pay electricity bill" maxLength={150} value={form.title} onChange={e=>setForm({...form,title:e.target.value})}/></label><label>Message (optional)<textarea rows={3} maxLength={1000} placeholder="What should I remember?" value={form.message} onChange={e=>setForm({...form,message:e.target.value})}/></label><label>Date & time<input type="datetime-local" required value={form.remind_at} onChange={e=>setForm({...form,remind_at:e.target.value})}/></label><button disabled={saving} type="submit" className="button button-primary">{saving?'Saving...':'Set reminder'} <Bell size={17}/></button></form></div>
      <div className="panel tasks-panel"><div className="panel-heading"><div><h2>Upcoming & due</h2><p>{pending.length} active reminders</p></div></div>{pending.length ? <div className="reminders-list">{pending.map(r=>{const due=new Date(r.remind_at)<=new Date();return <div className="reminder-item" key={r.id}><span className={`reminder-mark ${due?'due':''}`}><Bell size={18}/></span><div className="reminder-copy"><strong>{r.title}</strong>{r.message&&<p>{r.message}</p>}<small className={due?'overdue':''}>{due?'● Due now · ':''}{niceDate(r.remind_at)}</small></div><div className="reminder-actions"><IconButton icon={Check} label="Mark reminder done" onClick={()=>onAck(r)}/><IconButton icon={Trash2} label="Delete reminder" onClick={()=>onDelete(r)}/></div></div>})}</div>:<Empty icon={CalendarDays} title="Your calendar looks calm" text="Create a reminder for an important moment."/>}</div></div>
    {archived.length>0&&<div className="panel archived-panel"><div className="panel-heading"><div><h2>Completed reminders</h2><p>Things you've taken care of</p></div></div>{archived.map(r=><div className="archived-row" key={r.id}><CheckCircle2 size={17}/><span>{r.title}</span><small>{niceDate(r.remind_at)}</small><IconButton icon={Trash2} label="Delete reminder" onClick={()=>onDelete(r)}/></div>)}</div>}
  </>
}

function ExpenseScreen({ expenses, budget, month, setMonth, summary, onCreate, onUpdate, onDelete, onBudget, onUndo, undoAvailable }) {
  const [view, setView] = useState('dashboard')
  const [form, setForm] = useState(emptyExpense)
  const [editing, setEditing] = useState(null)
  const [limit, setLimit] = useState(String(budget?.amount || ''))
  const [saving, setSaving] = useState(false)
  const [exporting, setExporting] = useState('')
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [categoryFilter, setCategoryFilter] = useState('All')
  useEffect(() => setLimit(String(budget?.amount || '')), [budget?.amount])
  const finance = summary || {credit:0,debit:0,balance:0,count:0,categories:[],daily:[]}
  const spent = finance.debit
  const remaining = (budget?.amount || 0) - spent
  const pct = budget?.amount ? Math.min(100, spent/budget.amount*100) : 0
  const filtered = expenses.filter(x => (typeFilter === 'all' || x.entry_type === typeFilter) && (categoryFilter === 'All' || x.category === categoryFilter) && `${x.title} ${x.category} ${x.notes||''}`.toLowerCase().includes(search.toLowerCase()))
  const topCategory = finance.categories[0]?.total || 1
  const maxDay = Math.max(1, ...(finance.daily||[]).map(x=>Math.max(x.credit,x.debit)))
  const startEdit = item => {setForm({title:item.title,amount:String(item.amount),category:item.category,entry_type:item.entry_type||'debit',notes:item.notes||'',spent_on:item.spent_on});setEditing(item.id);setView('transactions');document.getElementById('transaction-form')?.scrollIntoView({behavior:'smooth',block:'center'})}
  const clearEdit = () => {setEditing(null);setForm(emptyExpense())}
  const submit = async e => {
    e.preventDefault();setSaving(true)
    try {const payload={...form, amount:Number(form.amount)}
      if (editing) await onUpdate(editing,payload)
      else await onCreate(payload)
      clearEdit()
    } finally {setSaving(false)}
  }
  const exportFile = async format => {
    setExporting(format)
    try {await downloadExpenseReport(format,month)} catch(err) {window.alert(err.message)} finally {setExporting('')}
  }
  const monthText = new Date(month+'-01T12:00:00').toLocaleDateString('en-IN',{month:'long',year:'numeric'})
  return <>
    <SectionHeading eyebrow="YOUR MONEY, CLEARLY" title="Expense & income tracker" subtitle="Track every credit and debit, undo mistakes, and download beautiful reports." action={<input className="month-input" aria-label="Select financial month" type="month" value={month} onChange={e=>setMonth(e.target.value)}/>}/>
    <div className="finance-top-actions">
      <div className="finance-tabbar"><button className={view==='dashboard'?'selected':''} onClick={()=>setView('dashboard')}><BarChart3 size={16}/> Dashboard</button><button className={view==='transactions'?'selected':''} onClick={()=>setView('transactions')}><ReceiptText size={16}/> Transactions</button></div>
      <div className="finance-downloads"><button className="button button-outline" title="Undo last transaction change" onClick={onUndo} disabled={!undoAvailable}><Undo2 size={16}/> Undo</button><button className="button button-soft" onClick={()=>{setView('transactions');clearEdit();setTimeout(()=>document.getElementById('transaction-form')?.scrollIntoView({behavior:'smooth'}),100)}}><Plus size={16}/> Create</button></div>
    </div>
    <div className="finance-grid finance-four">
      <div className="finance-stat"><span className="money-green"><TrendingDown size={20}/></span><p>Money in · Credit</p><strong className="credit-text">+{rupees(finance.credit)}</strong><small>{monthText}</small></div>
      <div className="finance-stat"><span className="money-orange"><TrendingUp size={20}/></span><p>Money out · Debit</p><strong className="debit-text">−{rupees(finance.debit)}</strong><small>{finance.count} entries total</small></div>
      <div className="finance-stat"><span><Wallet size={20}/></span><p>Net movement</p><strong className={finance.balance<0?'debit-text':'credit-text'}>{finance.balance<0?'−':'+'}{rupees(Math.abs(finance.balance))}</strong><small>Credit minus debit (not bank balance)</small></div>
      <div className="finance-stat"><span><Target size={20}/></span><p>Budget remaining</p><strong className={remaining<0?'debit-text':''}>{budget?.amount?rupees(remaining):'Not set'}</strong><small>{budget?.amount?`${Math.round(pct)}% of debit budget used`:'Add your monthly spending limit'}</small></div>
    </div>
    {view==='dashboard'&&<>
      <div className="finance-visuals">
        <div className="panel finance-dashboard-panel"><div className="panel-heading"><div><h2>Expenses by category</h2><p>Money out during {monthText}</p></div><span className="finance-panel-icon"><BarChart3 size={19}/></span></div>
          <div className="expense-chart-body">{finance.categories?.length?finance.categories.map((item,i)=><div className="expense-chart-line" key={item.category}><div className="expense-chart-label"><span><i className={`category-dot c${i%4}`}/>{item.category}</span><strong>{rupees(item.total)}</strong></div><div className="expense-chart-track"><div style={{width:`${100*item.total/topCategory}%`}}/></div></div>):<Empty icon={Wallet} title="No spending yet" text="Create your first debit to see category insights."/>}</div>
        </div>
        <div className="panel finance-dashboard-panel"><div className="panel-heading"><div><h2>Daily money flow</h2><p>Credit and debit activity</p></div><span className="finance-panel-icon"><Activity size={19}/></span></div>
          {finance.daily?.length?<div className="daily-money-chart">{finance.daily.map((d,i)=><div className="daily-chart-col" key={d.date} title={`${d.date}: Credit ${rupees(d.credit)}, Debit ${rupees(d.debit)}`}><div className="daily-chart-bars"><i className="bar-credit" style={{height:`${Math.max(d.credit>0?4:0,100*d.credit/maxDay)}%`}}/><i className="bar-debit" style={{height:`${Math.max(d.debit>0?4:0,100*d.debit/maxDay)}%`}}/></div><small>{d.date.slice(-2)}</small></div>)}</div>:<Empty icon={BarChart3} title="No activity yet" text="Your daily money flow will appear here."/>}
          <div className="finance-legend"><span><i className="legend-credit"/> Credit</span><span><i className="legend-debit"/> Debit</span></div>
        </div>
      </div>
      <div className="panel finance-dashboard-panel finance-bottom-panel"><div className="panel-heading"><div><h2>Budget & downloads</h2><p>Manage limits and export this month's report</p></div></div><div className="finance-budget-row"><form onSubmit={e=>{e.preventDefault();onBudget(Number(limit))}}><label>Monthly debit limit (₹)</label><div className="finance-budget-control"><input type="number" step="0.01" min="0" max="100000000" placeholder="e.g. 10000" value={limit} onChange={e=>setLimit(e.target.value)} required/><button type="submit" className="button button-primary">Save budget</button></div></form><div className="finance-budget-display"><div className="finance-budget-numbers"><span>Debit: {rupees(spent)}</span><span>Limit: {budget?.amount?rupees(budget.amount):'Not set'}</span></div><div className="budget-track"><div style={{width:`${pct}%`,background:remaining<0?'#f07769':undefined}}/></div></div></div>
        <div className="export-inline"><strong><Download size={16}/> Download report</strong><div>{[['pdf','PDF',FileText],['xlsx','Excel',FileSpreadsheet],['csv','CSV',Download]].map(([fmt,label,Icon])=><button className="button button-outline" disabled={!!exporting} key={fmt} onClick={()=>exportFile(fmt)}><Icon size={16}/>{exporting===fmt?'Preparing...':label}</button>)}</div></div>
      </div>
    </>}
    {view==='transactions'&&<div className="work-grid finance-work-grid"><div className="panel form-panel" id="transaction-form"><div className="panel-heading"><div><h2>{editing?'Edit transaction':'Create transaction'}</h2><p>Credit = money received, Debit = money spent</p></div><span className="form-top-icon"><Plus size={21}/></span></div>
      <form className="form-stack" onSubmit={submit}><label>Transaction title<input required maxLength={150} placeholder="e.g. Metro, Salary, Savings" value={form.title} onChange={e=>setForm({...form,title:e.target.value})}/></label><div className="finance-type-selector"><button type="button" className={form.entry_type==='debit'?'selected debit-selected':''} onClick={()=>setForm({...form,entry_type:'debit'})}><ArrowUpRight size={16}/> Debit · Money out</button><button type="button" className={form.entry_type==='credit'?'selected credit-selected':''} onClick={()=>setForm({...form,entry_type:'credit'})}><ArrowDownRight size={16}/> Credit · Money in</button></div>
        <div className="form-pair"><label>Amount (₹)<input type="number" min="0.01" max="100000000" step="0.01" required placeholder="250" value={form.amount} onChange={e=>setForm({...form,amount:e.target.value})}/></label><label>Category<select value={form.category} onChange={e=>setForm({...form,category:e.target.value})}>{expenseCategories.map(c=><option key={c}>{c}</option>)}</select></label></div><label>Date<input type="date" required value={form.spent_on} onChange={e=>setForm({...form,spent_on:e.target.value})}/></label><label>Notes (optional)<textarea maxLength={600} rows={3} placeholder="Payment method, description, etc." value={form.notes} onChange={e=>setForm({...form,notes:e.target.value})}/></label>
        <div className="finance-form-buttons"><button className="button button-primary" type="submit" disabled={saving}>{saving?'Saving...':editing?'Save changes':'Create transaction'} <ArrowRight size={17}/></button>{editing&&<button type="button" className="button button-outline" onClick={clearEdit}>Cancel</button>}</div></form></div>
      <div className="panel tasks-panel"><div className="panel-heading"><div><h2>Transaction history</h2><p>{filtered.length} of {expenses.length} transactions · {monthText}</p></div><button className="text-link" disabled={!undoAvailable} onClick={onUndo}><Undo2 size={16}/> Undo last</button></div>
        <div className="finance-filters"><div className="search-box"><Search size={16}/><input placeholder="Search title, category, notes" value={search} onChange={e=>setSearch(e.target.value)}/></div><select aria-label="Filter transaction type" value={typeFilter} onChange={e=>setTypeFilter(e.target.value)}><option value="all">All types</option><option value="debit">Debits</option><option value="credit">Credits</option></select><select aria-label="Filter category" value={categoryFilter} onChange={e=>setCategoryFilter(e.target.value)}><option value="All">All categories</option>{expenseCategories.map(c=><option key={c}>{c}</option>)}</select></div>
        {filtered.length?<div className="expense-list">{filtered.map(x=><div className="expense-row" key={x.id}><span className={`expense-icon ${x.entry_type==='credit'?'credit-icon':''}`}>{x.entry_type==='credit'?<ArrowDownRight size={18}/>:<ArrowUpRight size={18}/>}</span><div><strong>{x.title}</strong><small>{x.category} · {new Date(x.spent_on+'T12:00:00').toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'})}</small>{x.notes&&<small className="expense-notes">{x.notes}</small>}</div><strong className={`expense-amount ${x.entry_type==='credit'?'credit-text':'debit-text'}`}>{x.entry_type==='credit'?'+':'−'}{rupees(x.amount)}</strong><IconButton icon={Edit3} label="Edit transaction" onClick={()=>startEdit(x)}/><IconButton icon={Trash2} label="Delete transaction" onClick={()=>onDelete(x)}/></div>)}</div>:<Empty icon={Wallet} title="No matching transactions" text="Create a transaction or reset your filters."/>}
        <div className="finance-history-download"><span>Export all transactions for {monthText}</span><button className="button button-soft" onClick={()=>exportFile('xlsx')}><FileSpreadsheet size={16}/> Download Excel</button></div>
      </div></div>}
    <div className="notice finance-note"><ShieldCheck size={19}/><span>Transactions are stored in your local LifePilot database. Undo reverses the latest create, edit or delete action. Net movement is not your actual bank-account balance.</span></div>
  </>
}


function AssistantScreen({ config, messages, setMessages }) {
  const [input,setInput]=useState('')
  const [waiting,setWaiting]=useState(false)
  const endRef=useRef(null)
  useEffect(()=>endRef.current?.scrollIntoView({behavior:'smooth',block:'end'}),[messages,waiting])
  const ask=async text=>{const value=text.trim();if(!value||waiting)return;setInput('');setMessages(m=>[...m,{role:'user',text:value}]);setWaiting(true);try{const answer=await api('/assistant',{method:'POST',body:{message:value}});setMessages(m=>[...m,{role:'assistant',text:answer.reply,mode:answer.mode}])}catch(e){setMessages(m=>[...m,{role:'assistant',text:`Sorry, I couldn't respond: ${e.message}`,mode:'offline'}])}finally{setWaiting(false)}}
  return <><SectionHeading eyebrow="A LITTLE EXTRA CLARITY" title="Your smart assistant" subtitle="Get practical ideas for planning, productivity, and money." action={<Pill className={config?.ai_enabled?'pill-online':'count-pill'}><Sparkles size={13}/> {config?.ai_enabled?'AI connected':'Offline smart mode'}</Pill>}/>
    <div className="assistant-layout"><div className="panel chat-panel"><div className="chat-header"><div className="bot-icon"><Sparkles size={22}/></div><div><strong>LifePilot Assistant</strong><span><i className="online-dot"/> {config?.ai_enabled?'AI enabled':'Rule-based offline assistant'}</span></div></div><div className="chat-messages"><div className="chat-intro"><span><Sparkles size={24}/></span><h2>How can I help today?</h2><p>Ask about your schedule, priorities or expenses. I'll help you stay organized.</p></div>{messages.map((m,i)=><div key={i} className={`bubble-line ${m.role}`}><div className="bubble">{m.text}</div></div>)}{waiting&&<div className="bubble-line assistant"><div className="bubble typing">Thinking<span> • • •</span></div></div>}<div ref={endRef}/></div><form className="chat-input" onSubmit={e=>{e.preventDefault();ask(input)}}><input maxLength={2000} placeholder="Ask me anything about your day..." value={input} onChange={e=>setInput(e.target.value)} aria-label="Message for assistant"/><button disabled={waiting||!input.trim()} type="submit" aria-label="Send message"><Send size={19}/></button></form></div>
    <div className="chat-side"><div className="panel suggestion-panel"><h3>Try asking</h3><p>Not sure where to start?</p>{['Plan my day','How is my budget?','What are my reminders?','What should I focus on?'].map(s=><button key={s} onClick={()=>ask(s)}><MessageCircle size={17}/>{s}<ArrowRight size={15}/></button>)}</div><div className="assistant-tip"><Sparkles size={23}/><h3>Made for your goals</h3><p>{config?.ai_enabled?'AI replies use your current task and budget summary.':'Offline mode uses your real saved tasks, reminders and spending. Add an API key to enable generative AI.'}</p></div></div></div>
  </>
}

function SettingsScreen({ config, permission, onEnableNotify, onReload }) {
  return <><SectionHeading eyebrow="YOUR WORKSPACE" title="Settings & setup" subtitle="Know what is enabled, and customize how LifePilot works."/><div className="settings-grid"><div className="panel settings-panel"><h2>Connection status</h2><div className="setting-line"><span className="setting-icon"><ShieldCheck size={20}/></span><div><strong>Backend & local database</strong><small>Your data stays in local SQLite by default.</small></div><Pill className="pill-online">Connected</Pill></div><div className="setting-line"><span className="setting-icon"><Sparkles size={20}/></span><div><strong>Generative AI</strong><small>{config?.ai_enabled?'Enabled with a backend API key.':'Offline assistant active; add OPENAI_API_KEY to enable.'}</small></div><Pill className={config?.ai_enabled?'pill-online':'count-pill'}>{config?.ai_enabled?'Enabled':'Optional'}</Pill></div><div className="setting-line"><span className="setting-icon"><Bell size={20}/></span><div><strong>SMTP email reminders</strong><small>{config?.email_enabled?'Scheduled email delivery configured.':'Set SMTP details in backend/.env for email alerts.'}</small></div><Pill className={config?.email_enabled?'pill-online':'count-pill'}>{config?.email_enabled?'Configured':'Not set'}</Pill></div><div className="setting-line"><span className="setting-icon"><Bell size={20}/></span><div><strong>Browser notifications</strong><small>Only when the page is open and permission is granted.</small></div><button className="button button-soft" onClick={onEnableNotify}>{permission==='granted'?'Enabled':'Enable'}</button></div></div>
      <div className="panel settings-panel"><h2>Quick start tips</h2><div className="steps"><div><b>1</b><p><strong>Add tasks</strong><span>Prioritize college and personal work.</span></p></div><div><b>2</b><p><strong>Set reminders</strong><span>Schedule important dates and deadlines.</span></p></div><div><b>3</b><p><strong>Track spending</strong><span>Set a budget and record expenses.</span></p></div><div><b>4</b><p><strong>Talk to the assistant</strong><span>Get a quick plan for your day.</span></p></div></div><button className="button button-outline" onClick={onReload}><RefreshCw size={16}/> Refresh data</button></div></div>
    <div className="notice security-note"><ShieldCheck size={19}/><span><strong>Privacy note:</strong> This is a local single-user project with no login. Don't expose port 8000 on the public internet until authentication, HTTPS, access controls and backups are added. Generative AI, if enabled, sends a brief task/budget summary and your message to the configured AI provider.</span></div>
  </>
}

function App() {
  const [tab,setTab]=useState('overview')
  const [mobile,setMobile]=useState(false)
  const [month,setMonth]=useState(monthLocal())
  const [data,setData]=useState(null)
  const [tasks,setTasks]=useState([])
  const [reminders,setReminders]=useState([])
  const [expenses,setExpenses]=useState([])
  const [expenseSummary,setExpenseSummary]=useState(null)
  const [undoAvailable,setUndoAvailable]=useState(false)
  const [budget,setBudget]=useState({amount:0})
  const [config,setConfig]=useState(null)
  const [error,setError]=useState('')
  const [notice,setNotice]=useState('')
  const [alerts,setAlerts]=useState([])
  const [permission,setPermission]=useState('default')
  const seenNotifications=useRef(new Set())
  const [messages,setMessages]=useState([])

  const checkDue=useCallback(async()=>{
    try{
      const items=await api('/reminders/due')
      setAlerts(items)
      for(const item of items){
        if(!seenNotifications.current.has(item.id)){
          seenNotifications.current.add(item.id)
          if('Notification' in window && Notification.permission==='granted') new Notification(`LifePilot: ${item.title}`, {body:item.message||'Your reminder is due.'})
        }
      }
    }catch{/* main UI handles backend errors */}
  },[])
  const refresh=useCallback(async()=>{
    try{
      const [d,t,r,e,b,c,s,u]=await Promise.all([api(`/dashboard?month=${month}`),api('/tasks'),api('/reminders'),api(`/expenses?month=${month}`),api(`/budgets/${month}`),api('/config'),api(`/expenses/summary?month=${month}`),api('/expenses/undo-status')])
      setData(d);setTasks(t);setReminders(r);setExpenses(e);setBudget(b);setConfig(c);setExpenseSummary(s);setUndoAvailable(u.available);setError('')
      checkDue()
    }catch(e){setError(e.message)}
  },[month,checkDue])
  useEffect(()=>{refresh()},[refresh])
  useEffect(()=>{setPermission('Notification' in window ? Notification.permission : 'unsupported');const timer=setInterval(checkDue,30000);return()=>clearInterval(timer)},[checkDue])
  const mutate=async(fn,message)=>{try{await fn();await refresh();if(message){setNotice(message);setTimeout(()=>setNotice(''),4500)}}catch(e){setError(e.message);throw e}}
  const askConfirmDelete=async(entity, endpoint)=>{if(!window.confirm(`Delete "${entity.title}"?`))return;try{await mutate(()=>api(endpoint,{method:'DELETE'}),'Deleted successfully')}catch{/* message displayed */}}
  const toggle=async task=>{try{await mutate(()=>api(`/tasks/${task.id}`,{method:'PATCH',body:{completed:!task.completed}}))}catch{/* message displayed */}}
  const createTask=body=>mutate(()=>api('/tasks',{method:'POST',body}),'Task saved')
  const updateTask=(id,body)=>mutate(()=>api(`/tasks/${id}`,{method:'PATCH',body}),'Task updated')
  const createReminder=body=>mutate(()=>api('/reminders',{method:'POST',body}),'Reminder scheduled')
  const ack=async r=>{try{await mutate(()=>api(`/reminders/${r.id}/acknowledge`,{method:'PATCH'}),'Reminder marked done');setAlerts(a=>a.filter(x=>x.id!==r.id))}catch{/* message displayed */}}
  const createExpense=body=>mutate(()=>api('/expenses',{method:'POST',body}),'Transaction created · Undo available')
  const editExpense=(id,body)=>mutate(()=>api(`/expenses/${id}`,{method:'PATCH',body}),'Transaction updated · Undo available')
  const undoExpense=()=>mutate(()=>api('/expenses/undo',{method:'POST'}),'Last transaction change reversed')
  const setMonthlyBudget=amount=>mutate(()=>api(`/budgets/${month}`,{method:'PUT',body:{amount}}),'Budget updated')
  const enableNotify=async()=>{if(!('Notification' in window)){setNotice('This browser does not support desktop notifications.');return}const result=await Notification.requestPermission();setPermission(result);setNotice(result==='granted'?'Browser notifications are enabled.':'Notifications were not enabled.')}
  const jumpToAssistant=()=>{setTab('assistant');setMessages(m=>[...m, {role:'assistant',text:'Ready to plan? Choose “Plan my day” on the right, or ask me a question.',mode:'offline'}])}
  return <div className="app"><Sidebar tab={tab} setTab={setTab} mobile={mobile} closeMobile={()=>setMobile(false)} dueCount={alerts.length}/><div className="body-shell"><header className="topbar"><div className="top-left"><button className="hamburger" aria-label="Open menu" onClick={()=>setMobile(true)}><Menu size={23}/></button><div className="breadcrumbs"><span>Workspace</span><ChevronRight size={14}/><strong>{tab==='overview'?'Dashboard':tab==='assistant'?'AI Assistant':tab[0].toUpperCase()+tab.slice(1)}</strong></div></div><div className="top-right"><span className="date-chip"><CalendarDays size={16}/>{new Date().toLocaleDateString('en-IN',{weekday:'short',month:'short',day:'numeric',year:'numeric'})}</span><button className="top-notification" title="View reminders" onClick={()=>setTab('reminders')}><Bell size={19}/>{alerts.length>0&&<i/>}</button><span className="top-avatar">L</span></div></header>
      <main className="main-content">{error&&<div className="error-banner"><AlertTriangle size={18}/><span>{error}</span><button onClick={()=>{setError('');refresh()}}>Retry</button><IconButton icon={X} label="Dismiss error" onClick={()=>setError('')}/></div>}
        {tab==='overview'&&<Overview data={data} onTab={setTab} onToggle={toggle} onNewTask={()=>setTab('tasks')} onAsk={jumpToAssistant}/>}
        {tab==='tasks'&&<TaskScreen tasks={tasks} onCreate={createTask} onUpdate={updateTask} onToggle={toggle} onDelete={t=>askConfirmDelete(t,`/tasks/${t.id}`)}/>}
        {tab==='reminders'&&<ReminderScreen reminders={reminders} onCreate={createReminder} onAck={ack} onDelete={r=>askConfirmDelete(r,`/reminders/${r.id}`)} onEnableNotify={enableNotify} permission={permission}/>}
        {tab==='expenses'&&<ExpenseScreen expenses={expenses} summary={expenseSummary} budget={budget} month={month} setMonth={setMonth} onCreate={createExpense} onUpdate={editExpense} onUndo={undoExpense} undoAvailable={undoAvailable} onDelete={x=>askConfirmDelete(x,`/expenses/${x.id}`)} onBudget={setMonthlyBudget}/>}
        {tab==='assistant'&&<AssistantScreen config={config} messages={messages} setMessages={setMessages}/>}
        {tab==='settings'&&<SettingsScreen config={config} permission={permission} onEnableNotify={enableNotify} onReload={refresh}/>}
        <footer className="footer">LifePilot v2.0 <span>·</span> Make room for what matters.</footer>
      </main>
    </div>
    {notice&&<div className="toast"><CheckCircle2 size={19}/>{notice}<IconButton icon={X} label="Dismiss notice" onClick={()=>setNotice('')}/></div>}
    {alerts.length>0&&<div className="alert-stack">{alerts.slice(0,3).map(r=><div className="due-alert" key={r.id}><Bell size={20}/><div><strong>{r.title}</strong><p>{r.message||'Your reminder is due.'}</p></div><button onClick={()=>ack(r)}>Done</button></div>)}{alerts.length>3&&<p>+{alerts.length-3} more reminders</p>}</div>}
  </div>
}

createRoot(document.getElementById('root')).render(<React.StrictMode><App/></React.StrictMode>)