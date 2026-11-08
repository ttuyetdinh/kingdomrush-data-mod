// Number box: a plain input with up/down buttons, optional warning sign and an optional struck
// game value under it that resets on click. One element per box keeps big tables fast.
export default {
  template: `
    <span class="inline-flex flex-col items-end leading-none">
      <span class="inline-flex items-center gap-1">
        <span v-if="warning" class="text-amber-500 cursor-help text-sm" :title="warning">&#9888;</span>
        <span :class="boxClasses">
          <input
            class="min-w-0 flex-1 bg-transparent px-2 py-1 text-right font-mono text-sm outline-none"
            :class="inputTone"
            :value="inputValue"
            @input="onInput"
            @keydown.enter="$emit('commit')"
            @keydown.up.prevent="step(1, $event)"
            @keydown.down.prevent="step(-1, $event)"
            @blur="$emit('commit')"
          />
          <span class="flex flex-col justify-center border-l" :class="dark ? 'border-slate-600' : 'border-slate-200'">
            <button type="button" tabindex="-1" :class="arrowClasses" @mousedown.prevent @click="step(1, $event)">&#9650;</button>
            <button type="button" tabindex="-1" :class="arrowClasses" @mousedown.prevent @click="step(-1, $event)">&#9660;</button>
          </span>
        </span>
      </span>
      <span
        v-if="original !== null && original !== undefined"
        class="mt-0.5 cursor-pointer font-mono text-[11px] text-slate-400 hover:text-slate-700"
        title="Back to the game value"
        @click="$emit('reset')"
      ><span class="line-through">{{ original }}</span> &#8630;</span>
    </span>
  `,
  props: {
    value: String,
    original: String,
    warning: String,
    tone: String,
    boxClass: String,
    dark: Boolean,
  },
  data() {
    return { inputValue: this.value };
  },
  watch: {
    value(newValue) {
      this.inputValue = newValue;
    },
  },
  computed: {
    boxClasses() {
      const base = "inline-flex items-stretch rounded border focus-within:border-blue-500 " + (this.boxClass || "w-24");
      if (this.tone === "changed") return base + " bg-amber-100 border-amber-500";
      return base + (this.dark ? " bg-slate-800 border-slate-600 text-white" : " bg-white border-slate-300");
    },
    inputTone() {
      if (this.tone === "changed") return "font-bold text-amber-900";
      if (this.tone === "mixed") return "italic text-slate-400";
      if (this.tone === "pct-changed") return "font-bold text-amber-700";
      return "";
    },
    arrowClasses() {
      return "px-1 text-[8px] leading-[11px] text-blue-600 " + (this.dark ? "hover:bg-slate-700" : "hover:bg-slate-100");
    },
  },
  methods: {
    onInput(event) {
      this.inputValue = event.target.value;
      this.$emit("update:value", this.inputValue);
    },
    step(direction, event) {
      this.$emit("step", { direction: direction, shiftKey: !!event.shiftKey });
    },
  },
};
