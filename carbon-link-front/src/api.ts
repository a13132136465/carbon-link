const API = '/api/v1'

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message) }
}

function errorDetail(detail: unknown, status: number): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map(item => {
    const field = Array.isArray(item.loc) ? item.loc.slice(1).join('.') : ''
    return `${field ? `${field}: ` : ''}${item.msg || '输入无效'}`
  }).join('；')
  return `请求失败 (${status})`
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('carbonlink_token')
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })
  if (response.status === 401) {
    localStorage.removeItem('carbonlink_token')
    window.dispatchEvent(new Event('carbonlink:unauthorized'))
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new ApiError(response.status, errorDetail(body.detail, response.status))
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export async function requestPage<T>(path: string, options: RequestInit = {}): Promise<{data:T;total:number}> {
  const token = localStorage.getItem('carbonlink_token')
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })
  if (response.status === 401) {
    localStorage.removeItem('carbonlink_token')
    window.dispatchEvent(new Event('carbonlink:unauthorized'))
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new ApiError(response.status, errorDetail(body.detail, response.status))
  }
  return {data:await response.json() as T,total:Number(response.headers.get('X-Total-Count')||0)}
}

export const idempotencyKey = () => crypto.randomUUID()
export const json = (body: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(body) })

export async function uploadDocument<T>(projectId:string, category:string, file:File):Promise<T>{
  const token=localStorage.getItem('carbonlink_token')
  const response=await fetch(`${API}/projects/${projectId}/documents?category=${encodeURIComponent(category)}`,{method:'POST',body:file,headers:{'Content-Type':file.type,'X-File-Name':encodeURIComponent(file.name),...(token?{Authorization:`Bearer ${token}`}:{})}})
  if(!response.ok){const body=await response.json().catch(()=>({}));throw new ApiError(response.status,body.detail||`上传失败 (${response.status})`)}
  return response.json() as Promise<T>
}

export async function downloadDocument(projectId:string, documentId:string, filename:string){
  const token=localStorage.getItem('carbonlink_token')
  const response=await fetch(`${API}/projects/${projectId}/documents/${documentId}/download`,{headers:token?{Authorization:`Bearer ${token}`}:{}})
  if(!response.ok)throw new ApiError(response.status,'下载材料失败')
  const url=URL.createObjectURL(await response.blob()),link=document.createElement('a')
  link.href=url;link.download=filename;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)
}
