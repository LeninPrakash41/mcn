import React, { useState, useEffect, useCallback } from "react"
import { api } from "../services/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Plus, Search } from "lucide-react"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription, SheetFooter } from "@/components/ui/sheet"

export function MarketplaceCatalog() {
  const [items, setItems] = useState([])
  const [category, setCategory] = useState("All")
  const [search, setSearch] = useState("")
  const [active_tool, setActiveTool] = useState("All")
  const [selected_prompt, setSelectedPrompt] = useState(null)
  const [copy_status, setCopyStatus] = useState("")
  const [show_test_modal, setShowTestModal] = useState(false)
  const [edit_item, setEditItem] = useState<any>(null)
  const [edit_title, setEditTitle] = useState('')
  const [create_title, setCreateTitle] = useState('')
  const [edit_category, setEditCategory] = useState('')
  const [create_category, setCreateCategory] = useState('')
  const [edit_ai_tool, setEditAiTool] = useState('')
  const [create_ai_tool, setCreateAiTool] = useState('')
  const [edit_price, setEditPrice] = useState('')
  const [create_price, setCreatePrice] = useState('')
  const [edit_author, setEditAuthor] = useState('')
  const [create_author, setCreateAuthor] = useState('')
  const [edit_avg_rating, setEditAvgRating] = useState('')
  const [create_avg_rating, setCreateAvgRating] = useState('')
  const [edit_forks_count, setEditForksCount] = useState('')
  const [create_forks_count, setCreateForksCount] = useState('')
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
      const res = await api.post('/list_prompts', {category: category, search: search})
      setItems(res.data)
    })()
  }, [])
  const submit = useCallback(async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    const res = await api.post('/list_prompts', {category: category, search: search})
    setItems(res.data)
  }, [items, category, search, active_tool, selected_prompt, copy_status, show_test_modal])
  const handleEdit = useCallback((row: any) => {
    set_mcnEditItemId(row.id)
    setEditTitle((row as any).title ?? '')
    setEditCategory((row as any).category ?? '')
    setEditAiTool((row as any).ai_tool ?? '')
    setEditPrice((row as any).price ?? '')
    setEditAuthor((row as any).author ?? '')
    setEditAvgRating((row as any).avg_rating ?? '')
    setEditForksCount((row as any).forks_count ?? '')
    setEditItem(row)
    set_mcnShowEditModal(true)
  }, [])

  const handleDelete = useCallback(async (id: number) => {
    if (!window.confirm("Delete this marketplacecatalog?")) return
    await api.post('/delete_marketplacecatalog', { id })
    const _resp = await api.post('/list_marketplacecatalogs', {})
    setItems(_resp.data ?? _resp)
  }, [])

  const handleSave = useCallback(async () => {
    await api.post('/update_marketplacecatalog', { id: _mcnEditItemId, title: edit_title, category: edit_category, ai_tool: edit_ai_tool, price: edit_price, author: edit_author, avg_rating: edit_avg_rating, forks_count: edit_forks_count })
    set_mcnShowEditModal(false)
    const _resp = await api.post('/list_marketplacecatalogs', {})
    setItems(_resp.data ?? _resp)
  }, [_mcnEditItemId, edit_title, edit_category, edit_ai_tool, edit_price, edit_author, edit_avg_rating, edit_forks_count])

  const handleCreate = useCallback(async () => {
    await api.post('/create_marketplacecatalog', { title: create_title, category: create_category, ai_tool: create_ai_tool, price: create_price, author: create_author, avg_rating: create_avg_rating, forks_count: create_forks_count })
    set_mcnShowCreateModal(false)
    setCreateTitle('')
    setCreateCategory('')
    setCreateAiTool('')
    setCreatePrice('')
    setCreateAuthor('')
    setCreateAvgRating('')
    setCreateForksCount('')
    const _resp = await api.post('/list_marketplacecatalogs', {})
    setItems(_resp.data ?? _resp)
  }, [create_title, create_category, create_ai_tool, create_price, create_author, create_avg_rating, create_forks_count])

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
            <h2 className="text-xl font-semibold">{"Discover & Fork Prompts for Modern AI Tools"}</h2>
          </CardHeader>
          <CardContent className="pt-6">
            <form onSubmit={submit} className="space-y-4">
              <div className="grid grid-cols-3 gap-4">
                <div className="space-y-1">
                  <Label htmlFor="search">{"Search prompts, keywords, or tags"}</Label>
                  <Input value={search} onChange={(e) => setSearch(e.target.value)} />
                </div>
                <div className="space-y-1">
                  <Label>{"Filter Category"}</Label>
                  <Select value={category} onValueChange={setCategory}>
                    <SelectTrigger><SelectValue placeholder={"Select…"} /></SelectTrigger>
                    <SelectContent>
                      {["All", "Image & Art", "Coding & Tech", "Marketing & SEO", "AI Agents"].map((o: any) => <SelectItem key={String(o)} value={String(o)}>{String(o)}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <Button variant="default">{"Filter Catalog"}</Button>
              </div>
            </form>
          </CardContent>
        </Card>
        <Card >
          <CardHeader>
            <h2 className="text-xl font-semibold">{"Top Community Prompts & Workflows"}</h2>
          </CardHeader>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between pb-4">
              <div className="relative w-64">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <input type="text" placeholder="Search..." className="w-full rounded-md border border-input bg-background pl-9 pr-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
              </div>
              <button className="flex items-center gap-2 px-4 py-2 text-sm rounded bg-primary text-primary-foreground hover:bg-primary/90" onClick={() => set_mcnShowCreateModal(true)}>
                <Plus className="w-4 h-4" /> New Marketplacecatalog
              </button>
            </div>
            <Table >
              <TableHeader>
                <TableRow>
                  <TableHead >
                    {"title"}
                  </TableHead>
                  <TableHead >
                    {"category"}
                  </TableHead>
                  <TableHead >
                    {"ai_tool"}
                  </TableHead>
                  <TableHead >
                    {"price"}
                  </TableHead>
                  <TableHead >
                    {"author"}
                  </TableHead>
                  <TableHead >
                    {"avg_rating"}
                  </TableHead>
                  <TableHead >
                    {"forks_count"}
                  </TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {paginatedItems.map((row: any, i: number) => (
                  <TableRow key={i}>
                  <TableCell>{row.title}</TableCell>
                <TableCell>{row.category}</TableCell>
                <TableCell>{row.ai_tool}</TableCell>
                <TableCell>{row.price}</TableCell>
                <TableCell>{row.author}</TableCell>
                <TableCell>{row.avg_rating}</TableCell>
                <TableCell>{row.forks_count}</TableCell>
  
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
              <SheetTitle>Edit marketplacecatalog</SheetTitle>
              <SheetDescription>Update the details below.</SheetDescription>
            </SheetHeader>
            <div className="space-y-4 py-4">
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">title</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={edit_title} onChange={(e) => setEditTitle(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">category</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={edit_category} onChange={(e) => setEditCategory(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">ai_tool</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={edit_ai_tool} onChange={(e) => setEditAiTool(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">price</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={edit_price} onChange={(e) => setEditPrice(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">author</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={edit_author} onChange={(e) => setEditAuthor(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">avg_rating</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={edit_avg_rating} onChange={(e) => setEditAvgRating(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">forks_count</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={edit_forks_count} onChange={(e) => setEditForksCount(e.target.value)} />
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
              <SheetTitle>Create marketplacecatalog</SheetTitle>
              <SheetDescription>Enter the details below.</SheetDescription>
            </SheetHeader>
            <div className="space-y-4 py-4">
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">title</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={create_title} onChange={(e) => setCreateTitle(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">category</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={create_category} onChange={(e) => setCreateCategory(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">ai_tool</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={create_ai_tool} onChange={(e) => setCreateAiTool(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">price</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={create_price} onChange={(e) => setCreatePrice(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">author</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={create_author} onChange={(e) => setCreateAuthor(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">avg_rating</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={create_avg_rating} onChange={(e) => setCreateAvgRating(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium capitalize">forks_count</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={create_forks_count} onChange={(e) => setCreateForksCount(e.target.value)} />
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

export default MarketplaceCatalog
