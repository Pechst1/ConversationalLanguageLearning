import React from 'react';
import { Pressable, PressableProps, StyleSheet, Text } from 'react-native';
import { colors, spacing, fontFamilies, fontSizes } from '../tokens';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost';

interface ButtonProps extends PressableProps {
  label: string;
  variant?: ButtonVariant;
}

const disabledStyle = { opacity: 0.6 } as const;

export const Button: React.FC<ButtonProps> = ({ label, variant = 'primary', style, ...props }) => {
  const { container, label: labelStyle } = styles[variant];
  const isDisabled = Boolean(props.disabled);

  return (
    <Pressable style={[container, isDisabled && disabledStyle, style]} {...props}>
      <Text style={labelStyle}>{label}</Text>
    </Pressable>
  );
};

const baseContainer = {
  paddingVertical: spacing.sm,
  paddingHorizontal: spacing.lg,
  borderRadius: 999,
  alignItems: 'center' as const
};

const baseLabel = {
  fontFamily: fontFamilies.medium,
  fontSize: fontSizes.body,
  color: colors.text,
  letterSpacing: 0.4
};

const styles = {
  primary: StyleSheet.create({
    container: {
      ...baseContainer,
      backgroundColor: colors.primary
    },
    label: {
      ...baseLabel,
      color: '#FFFFFF'
    }
  }),
  secondary: StyleSheet.create({
    container: {
      ...baseContainer,
      backgroundColor: colors.surface,
      borderWidth: 1,
      borderColor: colors.border
    },
    label: {
      ...baseLabel
    }
  }),
  ghost: StyleSheet.create({
    container: {
      ...baseContainer,
      backgroundColor: 'transparent'
    },
    label: {
      ...baseLabel,
      color: colors.primary
    }
  })
} as const;
