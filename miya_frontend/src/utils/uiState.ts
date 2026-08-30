import { ref } from 'vue'

export const messageViewExpanded = ref(false)

export function setMessageViewExpanded(value: boolean) {
  messageViewExpanded.value = value
}
