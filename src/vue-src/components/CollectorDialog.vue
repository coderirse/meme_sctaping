<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { api } from '../utils/api'

const emit = defineEmits<{ saved: [] }>()
const visible = ref(false)
const source = ref('qq')
const env = ref<any>({ accounts: [], root: '' })
const account = ref('')
const job = ref<any>({ status: 'idle', items: [] })
const selected = ref(new Set<string>())
const onlyNew = ref(true)
const query = ref('')
const error = ref('')
const pending = ref(false)
const revision = ref(0)
let timer: ReturnType<typeof setTimeout> | undefined
let generation = 0
let notified = ''

const busy = computed(() => pending.value || ['scanning', 'saving'].includes(job.value.status))
const items = computed(() => (job.value.source === source.value ? job.value.items || [] : []).filter((item: any) =>
  (!onlyNew.value || !item.duplicate) && item.name.toLowerCase().includes(query.value.toLowerCase())))
const summary = computed(() => {
  const j = job.value
  if (j.status === 'scanning') return `正在扫描 ${j.done} / ${j.total}`
  if (j.status === 'saving') return `正在保存 ${j.done} / ${j.total}`
  if (j.status === 'done' || j.status === 'cancelled') {
    return `${j.status === 'cancelled' ? '已取消；' : ''}成功 ${j.imported || 0}，重复 ${j.duplicates || 0}，失败 ${j.failed || 0}`
  }
  return `候选 ${items.value.length}，已选 ${selected.value.size}`
})

async function poll(run = generation) {
  try {
    const result = await api('collector_status')
    if (!visible.value || run !== generation) return
    job.value = result || { status: 'idle', items: [] }
    if (result?.error) error.value = result.error
    const completed = `${result?.session}:${result?.status}:${result?.done}`
    if (['done', 'cancelled'].includes(result?.status) && completed !== notified) {
      notified = completed
      selected.value = new Set()
      emit('saved')
    }
  } catch (_) {
    error.value = '无法读取任务状态，请重新打开采集窗口'
  }
  if (visible.value && run === generation) timer = setTimeout(() => poll(run), 1000)
}

async function detect(pick = false) {
  selected.value = new Set()
  error.value = ''
  pending.value = true
  try {
    const result = await api(pick ? 'collector_pick_root' : 'collector_environment', source.value)
    if (!result) return
    env.value = result
    account.value = result.accounts?.some((a: any) => a.id === result.selected)
      ? result.selected : result.accounts?.[0]?.id || ''
    if (!result.ok) error.value = result.message || '未发现可用账号'
  } catch (_) {
    error.value = '环境检测失败，请手动选择数据目录'
  } finally { pending.value = false }
}

async function open(kind = 'qq') {
  source.value = kind
  visible.value = true
  selected.value = new Set()
  query.value = ''
  clearTimeout(timer)
  generation++
  await detect()
  poll(generation)
}

async function scan() {
  error.value = ''
  pending.value = true
  try {
    const result = await api('collector_scan', source.value, env.value.root, account.value)
    if (!result?.ok) error.value = result?.error || '无法开始扫描'
    else {
      selected.value = new Set()
      job.value = await api('collector_status')
    }
  } finally { pending.value = false }
}

function toggle(id: string) {
  const next = new Set(selected.value)
  next.has(id) ? next.delete(id) : next.add(id)
  selected.value = next
}

function selectVisible() {
  const eligible = items.value.filter((i: any) => !i.error && !i.duplicate)
  const all = eligible.every((i: any) => selected.value.has(i.id))
  selected.value = new Set(all ? [] : eligible.map((i: any) => i.id))
}

async function save() {
  pending.value = true
  try {
    const result = await api('collector_save', job.value.session, [...selected.value])
    if (!result?.ok) error.value = result?.error || '保存失败'
    else job.value = await api('collector_status')
  } finally { pending.value = false }
}

async function retry(id: string) {
  await api('collector_retry', id)
  job.value = await api('collector_status')
  revision.value++
}

async function close() {
  if (busy.value) await api('collector_cancel')
  visible.value = false
  generation++
  clearTimeout(timer)
  emit('saved')
}

onUnmounted(() => { generation++; clearTimeout(timer) })
defineExpose({ open })
</script>

<template>
  <div v-if="visible" class="collector-backdrop" @click.self="close" @keydown.esc.stop="close">
    <section class="collector-dialog" role="dialog" aria-modal="true" aria-labelledby="collector-title">
      <header>
        <div><h2 id="collector-title">收集聊天表情</h2><p>原文件保存，保留 GIF 和动态 WebP</p></div>
        <button class="btn btn-ghost" @click="close">{{ busy ? '取消并关闭' : '关闭' }}</button>
      </header>
      <div class="collector-controls">
        <select v-model="source" aria-label="采集来源" :disabled="busy" @change="detect()">
          <option value="qq">Windows QQ</option><option value="wechat">Windows 微信</option>
        </select>
        <select v-model="account" aria-label="账号" :disabled="busy">
          <option value="" disabled>选择账号</option>
          <option v-for="a in env.accounts" :key="a.id" :value="a.id">{{ a.label }}</option>
        </select>
        <button class="btn btn-secondary" :disabled="busy" @click="detect(true)">选择目录</button>
        <button class="btn btn-primary" :disabled="busy || !account" @click="scan">{{ source === 'qq' ? '扫描 QQ 缓存' : '读取微信表情' }}</button>
      </div>
      <p class="collector-hint">{{ source === 'qq' ? '请先收藏并打开表情面板加载。缓存可能包含已取消收藏的图片，请预览后选择。' : '请保持微信登录并打开添加的表情面板。手机微信可先添加表情，再到电脑读取；密钥仅在本机处理。' }}</p>
      <p class="collector-path" :title="env.root">来源：{{ env.root || '未检测到' }}</p>
      <div v-if="error || job.error" class="collector-error" role="alert">{{ error || job.error }}</div>
      <div class="collector-filters">
        <input v-model="query" aria-label="筛选候选" placeholder="按文件名筛选" />
        <label><input v-model="onlyNew" type="checkbox" /> 只看未保存</label>
        <button class="btn btn-ghost btn-sm" :disabled="busy" @click="selectVisible">全选 / 清空</button>
      </div>
      <div class="collector-grid" aria-label="表情候选">
        <article v-for="item in items" :key="item.id" :class="{ chosen: selected.has(item.id), invalid: item.error }">
          <label>
            <input type="checkbox" :checked="selected.has(item.id)" :disabled="busy || item.duplicate || !!item.error" @change="toggle(item.id)" />
            <img v-if="!item.error" :src="`/api/collector/${job.session}/${item.id}?v=${revision}`" loading="lazy" :alt="item.name" />
            <span v-else class="collector-file-error">{{ item.error }}</span>
            <span class="collector-name" :title="item.name">{{ item.name }}</span>
            <small>{{ item.duplicate ? '已保存' : item.animated ? '动态原图' : item.ext?.slice(1).toUpperCase() || '查看时读取原图' }}</small>
          </label>
          <button v-if="item.error" class="btn btn-ghost btn-sm" :disabled="busy" @click="retry(item.id)">重试</button>
        </article>
        <p v-if="!items.length" class="collector-empty">{{ busy ? '正在读取候选…' : '扫描后在此预览并选择喜欢的表情' }}</p>
      </div>
      <div v-if="job.errors?.length" class="collector-errors" role="status">
        <div v-for="(failure, i) in job.errors" :key="i">{{ failure.name }}：{{ failure.error }}</div>
      </div>
      <footer>
        <div><strong role="status">{{ summary }}</strong><p class="collector-path">保存到：{{ job.storage }}</p></div>
        <button class="btn btn-secondary" @click="api('collector_open_storage')">打开目录</button>
        <button v-if="busy" class="btn btn-secondary" @click="api('collector_cancel')">取消任务</button>
        <button class="btn btn-primary" :disabled="busy || !selected.size" @click="save">保存所选 {{ selected.size || '' }}</button>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.collector-backdrop { position: fixed; inset: 0; z-index: 450; background: #0009; display: flex; align-items: center; justify-content: center; padding: 16px; }
.collector-dialog { background: var(--surface); color: var(--fg); border: 1px solid var(--border); border-radius: var(--radius-lg); width: 920px; max-width: 100%; height: min(820px, 94vh); display: flex; flex-direction: column; padding: 20px; gap: 12px; box-shadow: var(--shadow-lg); }
header, footer, .collector-controls, .collector-filters { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
header { justify-content: space-between; }
h2 { font-size: 18px; margin: 0 0 4px; } p { margin: 0; font-size: 12px; color: var(--fg-secondary); }
select, .collector-filters > input { background: var(--bg); color: var(--fg); border: 1px solid var(--border); border-radius: 6px; padding: 8px; min-width: 0; }
.collector-controls select { max-width: 220px; } .collector-path { overflow-wrap: anywhere; font-size: 11px; }
.collector-hint { line-height: 1.6; } .collector-filters label { display: flex; align-items: center; gap: 5px; font-size: 12px; }
.collector-grid { flex: 1; min-height: 100px; overflow-y: auto; display: grid; grid-template-columns: repeat(auto-fill, minmax(125px, 1fr)); align-content: start; gap: 10px; }
article { padding: 8px; border: 1px solid var(--border); border-radius: 8px; background: var(--bg); min-width: 0; }
article.chosen { border-color: var(--primary); box-shadow: inset 0 0 0 1px var(--primary); }
article label { display: flex; flex-direction: column; gap: 5px; cursor: pointer; } article input { align-self: flex-start; }
article img { width: 100%; height: 110px; object-fit: contain; } .collector-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 11px; }
small { color: var(--fg-secondary); font-size: 11px; } .collector-error, .collector-file-error { color: #fca5a5; font-size: 12px; }
.collector-file-error { min-height: 110px; display: flex; align-items: center; overflow-wrap: anywhere; }
.collector-empty { grid-column: 1 / -1; margin: 30px auto; }
.collector-errors { max-height: 75px; overflow-y: auto; color: #fca5a5; font-size: 12px; }
footer { padding-top: 10px; border-top: 1px solid var(--border); font-size: 12px; } footer > div { flex: 1; min-width: 140px; }
button:focus-visible, input:focus-visible, select:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; }
@media (max-width: 540px) { .collector-dialog { padding: 12px; } .collector-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
