"use client";

type TextTagInputProps = {
  label: string;
  tags: string[];
  newValue: string;
  onNewValueChange: (value: string) => void;
  onAddTag: (value: string) => void;
  onRemoveTag: (value: string) => void;
  placeholder: string;
  inputName: string;
  suggestions?: string[];
  helperText?: string | null;
};

export function TextTagInput({
  label,
  tags,
  newValue,
  onNewValueChange,
  onAddTag,
  onRemoveTag,
  placeholder,
  inputName,
  suggestions = [],
  helperText,
}: TextTagInputProps) {
  return (
    <div className="stack">
      <label className="field">
        <span>{label}</span>
        <div className="token-input-row">
          <input
            type="text"
            name={inputName}
            value={newValue}
            autoComplete="off"
            autoCapitalize="words"
            autoCorrect="off"
            spellCheck={false}
            onChange={(event) => onNewValueChange(event.target.value)}
            placeholder={placeholder}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                onAddTag(newValue);
              }
            }}
          />
          <button type="button" className="ghost-button" onClick={() => onAddTag(newValue)}>
            Add
          </button>
        </div>
      </label>
      {helperText ? <p className="helper-text">{helperText}</p> : null}
      <div className="tag-row">
        {tags.map((tag) => (
          <button
            key={tag}
            type="button"
            className="tag is-removable"
            onClick={() => onRemoveTag(tag)}
          >
            {tag}
            <span>Remove</span>
          </button>
        ))}
      </div>
      {suggestions.length > 0 ? (
        <div className="tag-row">
          {suggestions.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              className="tag is-suggestion"
              onClick={() => onAddTag(suggestion)}
            >
              {suggestion}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
