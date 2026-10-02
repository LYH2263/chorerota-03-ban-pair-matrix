<template>
  <section class="week-card" style="margin-top:16px">
    <header><strong>禁配矩阵</strong> <span class="muted">某人不得做某任务，生成周表时自动规避</span></header>
    <form @submit.prevent="add" style="display:flex;gap:8px;flex-wrap:wrap;align-items:flex-start">
      <select v-model.number="memberId" style="flex:1;min-width:120px">
        <option :value="0" disabled>选择成员</option>
        <option v-for="m in assignableMembers" :key="m.id" :value="m.id">{{ m.name }}</option>
      </select>
      <select v-model.number="taskId" style="flex:1;min-width:120px">
        <option :value="0" disabled>选择任务</option>
        <option v-for="t in tasks" :key="t.id" :value="t.id">{{ t.title }}</option>
      </select>
      <button type="submit">添加禁配</button>
    </form>
    <p v-if="err" class="err">{{ err }}</p>
    <ul class="list">
      <li v-for="e in rows" :key="e.id">
        <span class="chip coral">{{ e.member_name }}</span>
        <span class="muted">不得做</span>
        <span class="chip">{{ e.task_title }}</span>
        <button class="ghost" style="margin-left:8px;padding:2px 8px" @click="remove(e.id)">删除</button>
      </li>
    </ul>
    <p v-if="!rows.length" class="muted">暂无禁配，生成结果与改造前一致。</p>
  </section>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { api, reasonText } from '../api'
const rows = ref([])
const members = ref([])
const tasks = ref([])
const memberId = ref(0)
const taskId = ref(0)
const err = ref('')
const assignableMembers = computed(() => members.value.filter(m => m.active && m.data_quality === 'clean'))
async function load() {
  const [e, m, t] = await Promise.all([api('/exclusions'), api('/members'), api('/tasks')])
  rows.value = e; members.value = m; tasks.value = t
}
async function add() {
  err.value = ''
  if (!memberId.value || !taskId.value) return
  try {
    await api('/exclusions', { method: 'POST', body: JSON.stringify({ member_id: memberId.value, task_id: taskId.value }) })
    memberId.value = 0; taskId.value = 0; await load()
  } catch (e) { err.value = reasonText(e.message) }
}
async function remove(id) {
  err.value = ''
  try { await api('/exclusions/' + id, { method: 'DELETE' }); await load() }
  catch (e) { err.value = reasonText(e.message) }
}
onMounted(load)
</script>
