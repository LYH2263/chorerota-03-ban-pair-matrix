<template>
  <section class="ban-panel">
    <h2 class="brand" style="font-size:17px">人任禁配矩阵</h2>
    <p class="muted">勾选「某人不得做某任务」；重复、指向停用/脏成员的禁配会被后端拒绝。仅影响之后生成的周表，不动旧周。</p>
    <form @submit.prevent="add" class="ban-form">
      <select v-model="memberId">
        <option :value="null" disabled>成员</option>
        <option v-for="m in activeCleanMembers" :key="m.id" :value="m.id">{{ m.name }}</option>
      </select>
      <span class="muted">不得做</span>
      <select v-model="taskId">
        <option :value="null" disabled>任务</option>
        <option v-for="t in tasks" :key="t.id" :value="t.id">{{ t.title }}</option>
      </select>
      <button type="submit">加禁配</button>
    </form>
    <p v-if="err" class="err">{{ errText }}</p>
    <ul class="list">
      <li v-for="b in bans" :key="b.id">
        <span class="chip coral">{{ b.member_name }}</span>
        <span class="muted">不得做</span>
        <span class="chip">{{ b.task_title }}</span>
        <button class="ghost ban-del" @click="remove(b.id)">解除</button>
      </li>
      <li v-if="!bans.length" class="muted">暂无禁配</li>
    </ul>
  </section>
</template>
<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { api } from '../api'

const props = defineProps({
  members: { type: Array, default: () => [] },
  tasks: { type: Array, default: () => [] },
  // 预设 member 或 task：成员页/任务页打开时先选好一侧
  presetMember: { type: Number, default: null },
  presetTask: { type: Number, default: null },
})
const emit = defineEmits(['changed'])

const bans = ref([])
const memberId = ref(props.presetMember)
const taskId = ref(props.presetTask)
const err = ref(null)

const activeCleanMembers = computed(() =>
  props.members.filter(m => m.active && m.data_quality === 'clean'))

const REASON_TEXT = {
  duplicate_ban: '该禁配已存在',
  member_not_found: '成员不存在',
  task_not_found: '任务不存在',
  member_ineligible: '停用或脏数据成员不可设禁配',
}

const errText = computed(() => {
  if (!err.value) return ''
  const d = err.value.detail
  if (d && d.reason === 'unassignable_slot') {
    return `无人可派：Day ${d.day} / 任务#${d.task_id} 的活跃 clean 成员全部被禁配，整次生成已取消`
  }
  return REASON_TEXT[err.value.message] || err.value.message
})

async function load() {
  err.value = null
  try { bans.value = await api('/bans') } catch (e) { err.value = e }
}
async function add() {
  err.value = null
  if (memberId.value == null || taskId.value == null) return
  try {
    await api('/bans', { method: 'POST', body: JSON.stringify({ member_id: memberId.value, task_id: taskId.value }) })
    await load(); emit('changed')
  } catch (e) { err.value = e }
}
async function remove(id) {
  err.value = null
  try { await api('/bans/' + id, { method: 'DELETE' }); await load(); emit('changed') }
  catch (e) { err.value = e }
}
watch(() => props.presetMember, v => { if (v != null) memberId.value = v })
watch(() => props.presetTask, v => { if (v != null) taskId.value = v })

onMounted(load)
defineExpose({ reload: load })
</script>
<style scoped>
.ban-panel { margin-top: 18px; border-top: 1px dashed var(--line); padding-top: 12px; }
.ban-form { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.ban-form select { width: auto; margin: 0; min-width: 110px; }
.ban-del { margin-left: 8px; padding: 3px 10px; font-size: 12px; }
</style>
