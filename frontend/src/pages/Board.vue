<template>
  <div>
    <h1 class="brand">本周看板</h1>
    <p class="muted">周卡片网格 · round-robin 落位后可去「对调」申请交换 · 禁配自动规避</p>
    <div style="display:flex;gap:8px;margin:12px 0">
      <button @click="generate">生成周表</button>
      <button class="ghost" @click="load">刷新</button>
    </div>
    <p v-if="err" class="err">{{ err }}</p>
    <p v-if="snapshot.length" class="muted" style="margin:8px 0">
      本周生成时禁配快照：
      <span v-for="(s, i) in snapshot" :key="i" class="chip coral">{{ s.member_name }} ✕ {{ s.task_title }}</span>
    </p>
    <div class="week-grid">
      <article v-for="d in days" :key="d" class="week-card">
        <header>Day {{ d }}</header>
        <div v-for="a in byDay(d)" :key="a.id">
          <span class="chip">{{ a.task_title }}</span>
          <span class="chip coral">{{ a.member_name }}</span>
        </div>
        <div v-for="g in gapsByDay(d)" :key="'gap' + g.task_id">
          <span class="chip">{{ g.task_title }}</span>
          <span class="chip gap">缺口</span>
        </div>
        <p v-if="!byDay(d).length && !gapsByDay(d).length" class="muted">空</p>
      </article>
    </div>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api, reasonText } from '../api'
const assigns = ref([])
const gaps = ref([])
const snapshot = ref([])
const days = [0,1,2,3,4,5,6]
const err = ref('')
const weekId = 1
function byDay(d) { return assigns.value.filter(a => a.day === d) }
function gapsByDay(d) { return gaps.value.filter(g => g.day === d) }
async function load() {
  err.value = ''
  try {
    const b = await api('/weeks/' + weekId + '/board')
    assigns.value = b.assignments || []
    gaps.value = b.gaps || []
    snapshot.value = await api('/weeks/' + weekId + '/exclusions')
  } catch (e) { err.value = reasonText(e.message) }
}
async function generate() {
  err.value = ''
  try { await api('/weeks/' + weekId + '/generate', { method: 'POST', body: '{}' }); await load() }
  catch (e) { err.value = reasonText(e.message) }
}
onMounted(load)
</script>
