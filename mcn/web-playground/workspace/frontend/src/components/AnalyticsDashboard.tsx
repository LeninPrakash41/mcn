import React, { useState, useEffect, useCallback } from "react"
import { api } from "../services/api"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import { Plus, Search, TrendingUp } from "lucide-react"
import { Label } from "@/components/ui/label"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription, SheetFooter } from "@/components/ui/sheet"

export function AnalyticsDashboard() {
  const [total_revenue, setTotalRevenue] = useState("$476,500")
  const [deal_count, setDealCount] = useState(8)
  const [avg_deal, setAvgDeal] = useState("$59,562")
  const [items, setItems] = useState([])
  const [category_data, setCategoryData] = useState([])
  const [trend_data, setTrendData] = useState([])
  const [report_text, setReportText] = useState("")
  const [loading, setLoading] = useState(false)
  const [edit_item, setEditItem] = useState<any>(null)
  const [edit_id, setEditId] = useState('')
  const [create_id, setCreateId] = useState('')
  const [edit_customer, setEditCustomer] = useState('')
  const [create_customer, setCreateCustomer] = useState('')
  const [edit_region, setEditRegion] = useState('')
  const [create_region, setCreateRegion] = useState('')
  const [edit_category, setEditCategory] = useState('')
  const [create_category, setCreateCategory] = useState('')
  const [edit_amount, setEditAmount] = useState('')
  const [create_amount, setCreateAmount] = useState('')
  const [edit_status, setEditStatus] = useState('')
  const [create_status, setCreateStatus] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const filteredItems = React.useMemo(() => {
    if (!searchQuery) return items;
    return items.filter((item: any) => 
      Object.values(item).some(v => 
        String(v).toLowerCase().includes(searchQuery.toLowerCase())
      )
    )
  }, [items, searchQuery])
  const [_mcnEditItemId, set_mcnEditItemId] = useState<number | null>(null)
  const [_mcnShowEditModal, set_mcnShowEditModal] = useState(false)
  const [_mcnShowCreateModal, set_mcnShowCreateModal] = useState(false)

  useEffect(() => {
    ;(async () => {
      const res = await api.post('/get_dashboard', {})
      if (res.success) {
        setItems(res.data)
        setCategoryData(res.categories.items)
        setTrendData(res.trends)
      }
      const rep_res = await api.post('/export_executive_report', {arg0: "markdown"})
      if (rep_res.success) {
        setReportText(rep_res.report)
      }
    })()
  }, [])
  const handleEdit = useCallback((row: any) => {
    set_mcnEditItemId(row.id)
    setEditId((row as any).id ?? '')
    setEditCustomer((row as any).customer ?? '')
    setEditRegion((row as any).region ?? '')
    setEditCategory((row as any).category ?? '')
    setEditAmount((row as any).amount ?? '')
    setEditStatus((row as any).status ?? '')
    setEditItem(row)
    set_mcnShowEditModal(true)
  }, [])

  const handleDelete = useCallback(async (id: number) => {
    if (!window.confirm("Delete this analyticsdashboard?")) return
    await api.post('/delete_analyticsdashboard', { id })
    const _resp = await api.post('/list_analyticsdashboards', {})
    setItems(_resp.data ?? _resp)
  }, [])

  const handleSave = useCallback(async () => {
    await api.post('/update_analyticsdashboard', { id: _mcnEditItemId, id: edit_id, customer: edit_customer, region: edit_region, category: edit_category, amount: edit_amount, status: edit_status })
    set_mcnShowEditModal(false)
    const _resp = await api.post('/list_analyticsdashboards', {})
    setItems(_resp.data ?? _resp)
  }, [_mcnEditItemId, edit_id, edit_customer, edit_region, edit_category, edit_amount, edit_status])

  const handleCreate = useCallback(async () => {
    await api.post('/create_analyticsdashboard', { id: create_id, customer: create_customer, region: create_region, category: create_category, amount: create_amount, status: create_status })
    set_mcnShowCreateModal(false)
    setCreateId('')
    setCreateCustomer('')
    setCreateRegion('')
    setCreateCategory('')
    setCreateAmount('')
    setCreateStatus('')
    const _resp = await api.post('/list_analyticsdashboards', {})
    setItems(_resp.data ?? _resp)
  }, [create_id, create_customer, create_region, create_category, create_amount, create_status])

  const paginatedItems = React.useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredItems.slice(start, start + pageSize);
  }, [filteredItems, currentPage, pageSize])

  const totalPages = Math.ceil(filteredItems.length / pageSize);


  return (
    <>
      <Card >
        <CardHeader>
          <h2 className="text-xl font-semibold">{"Executive Analytics & Performance BI"}</h2>
        </CardHeader>
        <CardContent className="pt-6">
          <div className="grid grid-cols-3 gap-4">
            <Card>
              <CardContent className="p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">{"Total Revenue"}</p>
                    <p className="text-2xl font-bold mt-1">{total_revenue}<span className="text-sm font-normal ml-1 text-muted-foreground">{""}</span></p>
                    
                  </div>
                  <div className="p-2 rounded-lg text-primary bg-primary/10">
                    <TrendingUp className="w-5 h-5" />
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">{"Total Deals"}</p>
                    <p className="text-2xl font-bold mt-1">{deal_count}<span className="text-sm font-normal ml-1 text-muted-foreground">{""}</span></p>
                    
                  </div>
                  <div className="p-2 rounded-lg text-primary bg-primary/10">
                    <TrendingUp className="w-5 h-5" />
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">{"Avg Deal Size"}</p>
                    <p className="text-2xl font-bold mt-1">{avg_deal}<span className="text-sm font-normal ml-1 text-muted-foreground">{""}</span></p>
                    
                  </div>
                  <div className="p-2 rounded-lg text-primary bg-primary/10">
                    <TrendingUp className="w-5 h-5" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={category_data}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey={"category"} />
                <YAxis />
                <Tooltip />
                <Bar dataKey={"amount"} fill="#6366f1" />
              </BarChart>
            </ResponsiveContainer>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={trend_data}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey={"period"} />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey={"value"} stroke="#6366f1" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <Separator  />
        </CardContent>
        <CardHeader>
          <h2 className="text-xl font-semibold">{"Recent Transactions"}</h2>
        </CardHeader>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between pb-4">
            <div className="relative w-64">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <input type="text" placeholder="Search..." className="w-full rounded-md border border-input bg-background pl-9 pr-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
            </div>
            <button className="flex items-center gap-2 px-4 py-2 text-sm rounded bg-primary text-primary-foreground hover:bg-primary/90" onClick={() => set_mcnShowCreateModal(true)}>
              <Plus className="w-4 h-4" /> New Analyticsdashboard
            </button>
          </div>
          <Table >
            <TableHeader>
              <TableRow>
                <TableHead >
                  {"id"}
                </TableHead>
                <TableHead >
                  {"customer"}
                </TableHead>
                <TableHead >
                  {"region"}
                </TableHead>
                <TableHead >
                  {"category"}
                </TableHead>
                <TableHead >
                  {"amount"}
                </TableHead>
                <TableHead >
                  {"status"}
                </TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {paginatedItems.map((row: any, i: number) => (
                <TableRow key={i}>
                <TableCell>{row.id}</TableCell>
              <TableCell>{row.customer}</TableCell>
              <TableCell>{row.region}</TableCell>
              <TableCell>{row.category}</TableCell>
              <TableCell>{row.amount}</TableCell>
              <TableCell>{row.status}</TableCell>
  
              <TableCell>
                <button
                  className="mr-2 text-xs px-2 py-1 bg-blue-100 text-blue-800 rounded hover:bg-blue-200"
                  onClick={() => handleEdit(row)}
                >Edit</button>
                <button
                  className="text-xs px-2 py-1 bg-red-100 text-red-800 rounded hover:bg-red-200"
                  onClick={() => handleDelete(row.id)}
                >Delete</button>
              </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div className="flex items-center justify-between px-4 py-3 border-t">
            <div className="text-sm text-muted-foreground">
              Showing {(currentPage - 1) * pageSize + 1} to {Math.min(currentPage * pageSize, filteredItems.length)} of {filteredItems.length} entries
            </div>
            <div className="flex items-center space-x-2">
              <button className="px-3 py-1 text-sm border rounded hover:bg-accent disabled:opacity-50" onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage === 1}>Previous</button>
              <button className="px-3 py-1 text-sm border rounded hover:bg-accent disabled:opacity-50" onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))} disabled={currentPage === totalPages || totalPages === 0}>Next</button>
            </div>
          </div>
        </CardContent>
      </Card>
        <Sheet open={_mcnShowEditModal} onOpenChange={set_mcnShowEditModal}>
          <SheetContent className="sm:max-w-md overflow-y-auto">
            <SheetHeader>
              <SheetTitle>Edit analyticsdashboard</SheetTitle>
              <SheetDescription>Update the details below.</SheetDescription>
            </SheetHeader>
            <div className="space-y-4 py-4">
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">id</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={edit_id} onChange={(e) => setEditId(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">customer</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={edit_customer} onChange={(e) => setEditCustomer(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">region</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={edit_region} onChange={(e) => setEditRegion(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">category</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={edit_category} onChange={(e) => setEditCategory(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">amount</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={edit_amount} onChange={(e) => setEditAmount(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">status</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={edit_status} onChange={(e) => setEditStatus(e.target.value)} />
            </div>
            </div>
            <SheetFooter>
              <button className="px-4 py-2 text-sm rounded border hover:bg-slate-50" onClick={() => set_mcnShowEditModal(false)}>Cancel</button>
              <button className="px-4 py-2 text-sm rounded bg-primary text-primary-foreground hover:bg-primary/90" onClick={handleSave}>Save Changes</button>
            </SheetFooter>
          </SheetContent>
        </Sheet>
  
        <Sheet open={_mcnShowCreateModal} onOpenChange={set_mcnShowCreateModal}>
          <SheetContent className="sm:max-w-md overflow-y-auto">
            <SheetHeader>
              <SheetTitle>Create analyticsdashboard</SheetTitle>
              <SheetDescription>Enter the details below.</SheetDescription>
            </SheetHeader>
            <div className="space-y-4 py-4">
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">id</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={create_id} onChange={(e) => setCreateId(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">customer</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={create_customer} onChange={(e) => setCreateCustomer(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">region</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={create_region} onChange={(e) => setCreateRegion(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">category</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={create_category} onChange={(e) => setCreateCategory(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">amount</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={create_amount} onChange={(e) => setCreateAmount(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">status</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={create_status} onChange={(e) => setCreateStatus(e.target.value)} />
            </div>
            </div>
            <SheetFooter>
              <button className="px-4 py-2 text-sm rounded border hover:bg-slate-50" onClick={() => set_mcnShowCreateModal(false)}>Cancel</button>
              <button className="px-4 py-2 text-sm rounded bg-primary text-primary-foreground hover:bg-primary/90" onClick={handleCreate}>Create</button>
            </SheetFooter>
          </SheetContent>
        </Sheet>
    </>
  )
}

export default AnalyticsDashboard
