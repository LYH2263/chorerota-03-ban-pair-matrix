<template>
  <div>
    <h1 class="brand">本周看板</h1>
    <p class="muted">周卡片网格 · round-robin 落位时自动规避禁配 · 生成当周钉住禁配快照，之后改矩阵不重切本周</p>
    <div style="display:flex;gap:8px;margin:12px 0">
      <button @click="generate">生成周表</button>
      <button class="ghost" @click="load">刷新</button>
    </div>
    <p v-if="err" class="err">{{ err }}</p>
    <div v-if="snapshot && snapshot.pinned" class="snap-bar">
      <strong>本周钉版禁配（{{ snapshot.bans.length }}）：</strong>
      <span v-for="b in snapshot.bans" :key="b.member_id + '-' + b.task_id" class="chip coral">
        {{ b.member_name }} ≠ {{ b.task_title }}
      </span>
      <span v-if="!snapshot.bans.length" class="muted">无（空快照）</span>
    </div>
    <p v-else class="muted">尚未生成，无钉版快照</p>
    <div class="week-grid">
      <article v-for="d in days" :key="d" class="week-card">
        <header>Day {{ d }}</header>
        <div v-for="a in byDay(d)" :key="a.id">
          <span class="chip">{{ a.task_title }}</span>
          <span class="chip coral">{{ a.member_name }}</span>
        </div>
        <p v-if="!byDay(d).length" class="muted">空</p>
      </article>
    </div>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
const assigns = ref([])
const snapshot = ref(null)
const days = [0,1,2,3,4,5,6]
const err = ref('')
const weekId = 1
function byDay(d) { return assigns.value.filter(a => a.day === d) }
async function load() {
  err.value = ''
  try {
    const b = await api('/weeks/' + weekId + '/board')
    assigns.value = b.assignments || []
    snapshot.value = b.ban_snapshot || null
  } catch (e) { err.value = e.message }
}
async function generate() {
  err.value = ''
  try {
    await api('/weeks/' + weekId + '/generate', { method: 'POST', body: '{}' })
    await load()
  } catch (e) {
    // 整次生成失败：后端已回滚，旧表旧快照原样；刷新一次确认看板仍是旧表
    if (e.detail && e.detail.reason === 'unassignable_slot') {
      err.value = `生成失败：Day ${e.detail.day} 的任务#${e.detail.task_id} 无人可派（活跃 clean 成员均被禁配），原周表已保留`
    } else {
      err.value = e.message
    }
    await load()
  }
}
onMounted(load)
</script>
<style scoped>
.snap-bar {
  background: var(--card); border: 1px dashed var(--line); border-radius: 12px;
  padding: 8px 12px; margin-bottom: 12px; font-size: 13px;
}
</style>
