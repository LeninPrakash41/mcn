import React, { useState, useEffect, useCallback } from "react"
import { api } from "../services/api"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import { Plus, Search, TrendingUp } from "lucide-react"
import { Label } from "@/components/ui/label"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription, SheetFooter } from "@/components/ui/sheet"

export function CreatorAnalytics() {
  const [total_prompts, setTotalPrompts] = useState(5)
  const [total_forks, setTotalForks] = useState(13490)
  const [gross_volume, setGrossVolume] = useState("$68,450.00")
  const [category_data, setCategoryData] = useState([])
  const [recent_reviews, setRecentReviews] = useState([])
  const [report_md, setReportMd] = useState("")
  const [edit_item, setEditItem] = useState<any>(null)
  const [edit_prompt_title, setEditPromptTitle] = useState('')
  const [create_prompt_title, setCreatePromptTitle] = useState('')
  const [edit_reviewer, setEditReviewer] = useState('')
  const [create_reviewer, setCreateReviewer] = useState('')
  const [edit_rating, setEditRating] = useState('')
  const [create_rating, setCreateRating] = useState('')
  const [edit_comment, setEditComment] = useState('')
  const [create_comment, setCreateComment] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const filteredItems = React.useMemo(() => {
    if (!searchQuery) return category_data;
    return category_data.filter((item: any) => 
      Object.values(item).some(v => 
        String(v).toLowerCase().includes(searchQuery.toLowerCase())
      )
    )
  }, [category_data, searchQuery])
  const [_mcnEditItemId, set_mcnEditItemId] = useState<number | null>(null)
  const [_mcnShowEditModal, set_mcnShowEditModal] = useState(false)
  const [_mcnShowCreateModal, set_mcnShowCreateModal] = useState(false)

  useEffect(() => {
    ;(async () => {
      const res = await api.post('/get_marketplace_analytics', {})
      if (res.success) {
        setTotalPrompts(res.total_prompts)
        setTotalForks(res.total_forks)
        setGrossVolume(res.gross_volume)
        setCategoryData(res.category_distribution)
        setRecentReviews(res.recent_reviews)
        setReportMd(res.report_md)
      }
    })()
  }, [])
  const handleEdit = useCallback((row: any) => {
    set_mcnEditItemId(row.id)
    setEditPromptTitle((row as any).prompt_title ?? '')
    setEditReviewer((row as any).reviewer ?? '')
    setEditRating((row as any).rating ?? '')
    setEditComment((row as any).comment ?? '')
    setEditItem(row)
    set_mcnShowEditModal(true)
  }, [])

  const handleDelete = useCallback(async (id: number) => {
    if (!window.confirm("Delete this creatoranalytic?")) return
    await api.post('/delete_creatoranalytic', { id })
    const _resp = await api.post('/list_creatoranalytics', {})
    setCategoryData(_resp.data ?? _resp)
  }, [])

  const handleSave = useCallback(async () => {
    await api.post('/update_creatoranalytic', { id: _mcnEditItemId, prompt_title: edit_prompt_title, reviewer: edit_reviewer, rating: edit_rating, comment: edit_comment })
    set_mcnShowEditModal(false)
    const _resp = await api.post('/list_creatoranalytics', {})
    setCategoryData(_resp.data ?? _resp)
  }, [_mcnEditItemId, edit_prompt_title, edit_reviewer, edit_rating, edit_comment])

  const handleCreate = useCallback(async () => {
    await api.post('/create_creatoranalytic', { prompt_title: create_prompt_title, reviewer: create_reviewer, rating: create_rating, comment: create_comment })
    set_mcnShowCreateModal(false)
    setCreatePromptTitle('')
    setCreateReviewer('')
    setCreateRating('')
    setCreateComment('')
    const _resp = await api.post('/list_creatoranalytics', {})
    setCategoryData(_resp.data ?? _resp)
  }, [create_prompt_title, create_reviewer, create_rating, create_comment])

  const paginatedItems = React.useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredItems.slice(start, start + pageSize);
  }, [filteredItems, currentPage, pageSize])

  const totalPages = Math.ceil(filteredItems.length / pageSize);


  return (
    <>
      <div >
        <Card >
          <CardHeader>
            <h2 className="text-xl font-semibold">{"Marketplace Intelligence & Creator Performance"}</h2>
          </CardHeader>
          <CardContent className="pt-6">
            <div className="grid grid-cols-3 gap-4">
              <Card>
                <CardContent className="p-5">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-muted-foreground">{"Total Prompts"}</p>
                      <p className="text-2xl font-bold mt-1">{total_prompts}<span className="text-sm font-normal ml-1 text-muted-foreground">{""}</span></p>
                      
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
                      <p className="text-sm font-medium text-muted-foreground">{"Total Community Forks"}</p>
                      <p className="text-2xl font-bold mt-1">{total_forks}<span className="text-sm font-normal ml-1 text-muted-foreground">{""}</span></p>
                      
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
                      <p className="text-sm font-medium text-muted-foreground">{"Gross Platform Volume"}</p>
                      <p className="text-2xl font-bold mt-1">{gross_volume}<span className="text-sm font-normal ml-1 text-muted-foreground">{""}</span></p>
                      
                    </div>
                    <div className="p-2 rounded-lg text-primary bg-primary/10">
                      <TrendingUp className="w-5 h-5" />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </CardContent>
        </Card>
        <Card >
          <CardHeader>
            <h2 className="text-xl font-semibold">{"Forks by Category Distribution"}</h2>
          </CardHeader>
          <CardContent className="pt-6">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={category_data}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey={"category"} />
                <YAxis />
                <Tooltip />
                <Bar dataKey={"value"} fill="#6366f1" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card >
          <CardHeader>
            <h2 className="text-xl font-semibold">{"Community Reviews & Feedback"}</h2>
          </CardHeader>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between pb-4">
              <div className="relative w-64">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <input type="text" placeholder="Search..." className="w-full rounded-md border border-input bg-background pl-9 pr-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
              </div>
              <button className="flex items-center gap-2 px-4 py-2 text-sm rounded bg-primary text-primary-foreground hover:bg-primary/90" onClick={() => set_mcnShowCreateModal(true)}>
                <Plus className="w-4 h-4" /> New Creatoranalytic
              </button>
            </div>
            <Table >
              <TableHeader>
                <TableRow>
                  <TableHead >
                    {"prompt_title"}
                  </TableHead>
                  <TableHead >
                    {"reviewer"}
                  </TableHead>
                  <TableHead >
                    {"rating"}
                  </TableHead>
                  <TableHead >
                    {"comment"}
                  </TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {paginatedItems.map((row: any, i: number) => (
                  <TableRow key={i}>
                  <TableCell>{row.prompt_title}</TableCell>
                <TableCell>{row.reviewer}</TableCell>
                <TableCell>{row.rating}</TableCell>
                <TableCell>{row.comment}</TableCell>
  
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
      </div>
        <Sheet open={_mcnShowEditModal} onOpenChange={set_mcnShowEditModal}>
          <SheetContent className="sm:max-w-md overflow-y-auto">
            <SheetHeader>
              <SheetTitle>Edit creatoranalytic</SheetTitle>
              <SheetDescription>Update the details below.</SheetDescription>
            </SheetHeader>
            <div className="space-y-4 py-4">
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">prompt_title</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={edit_prompt_title} onChange={(e) => setEditPromptTitle(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">reviewer</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={edit_reviewer} onChange={(e) => setEditReviewer(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">rating</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={edit_rating} onChange={(e) => setEditRating(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">comment</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={edit_comment} onChange={(e) => setEditComment(e.target.value)} />
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
              <SheetTitle>Create creatoranalytic</SheetTitle>
              <SheetDescription>Enter the details below.</SheetDescription>
            </SheetHeader>
            <div className="space-y-4 py-4">
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">prompt_title</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={create_prompt_title} onChange={(e) => setCreatePromptTitle(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">reviewer</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={create_reviewer} onChange={(e) => setCreateReviewer(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">rating</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={create_rating} onChange={(e) => setCreateRating(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">comment</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={create_comment} onChange={(e) => setCreateComment(e.target.value)} />
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

export default CreatorAnalytics
