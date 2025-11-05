import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { View, StyleSheet } from 'react-native';
import { Button, Text, colors, spacing } from '../ui';
import { Ionicons } from '@expo/vector-icons';
import { Button, Card, Text, colors, spacing } from '../ui';
import { useLearnerContext } from '../context/LearnerContext';
import type { AnkiWordProgress } from '../types/api';

export interface AppNavigatorProps {
  onSignOut: () => void;
}

type HomeStackParamList = {
  Home: undefined;
};

type TabParamList = {
  Learn: undefined;
  Profile: undefined;
};

const HomeStack = createNativeStackNavigator<HomeStackParamList>();
const Tab = createBottomTabNavigator<TabParamList>();

const ratingOptions = [
  { label: 'Again', rating: 0 },
  { label: 'Hard', rating: 1 },
  { label: 'Good', rating: 2 },
  { label: 'Easy', rating: 3 },
] as const;

const ProfileScreen: React.FC<{ onSignOut: () => void }> = ({ onSignOut }) => (
  <View style={styles.centered}>
    <Text variant="headline" emphasis="bold">
      Profile
    </Text>
    <Text color="textSecondary" style={styles.profileCopy}>
      Track streaks, achievements, and adjust learning preferences.
    </Text>
    <Button label="Sign out" variant="secondary" onPress={onSignOut} style={styles.signOutButton} />
  </View>
);

const HomeStackNavigator: React.FC = () => (
  <HomeStack.Navigator>
    <HomeStack.Screen name="Home" options={{ title: 'Reviews' }}>
      {() => <LearnScreen />}
    </HomeStack.Screen>
  </HomeStack.Navigator>
);

interface AppNavigatorProps {
  onSignOut: () => void;
}

export const AppNavigator: React.FC<AppNavigatorProps> = ({ onSignOut }) => (
  <Tab.Navigator
    screenOptions={({ route }) => ({
      headerShown: false,
      tabBarActiveTintColor: colors.primary,
      tabBarInactiveTintColor: colors.textSecondary,
      tabBarIcon: ({ color, size }) => {
        const iconName = route.name === 'Learn' ? 'book' : 'person-circle';
        return <Ionicons name={iconName as const} size={size} color={color} />;
      },
    })}
  >
    <Tab.Screen name="Learn" component={HomeStackNavigator} />
    <Tab.Screen name="Profile">
      {() => <ProfileScreen onSignOut={onSignOut} />}
    </Tab.Screen>
  </Tab.Navigator>
);

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  listContent: {
    padding: spacing.lg,
    paddingBottom: spacing.xxl,
  },
  header: {
    marginBottom: spacing.lg,
  },
  headerTitle: {
    marginBottom: spacing.sm,
  },
  headerSubtitle: {
    marginBottom: spacing.lg,
  },
  summaryRow: {
    flexDirection: 'row',
    marginBottom: spacing.lg,
  },
  summaryCard: {
    flex: 1,
  },
  summaryCardSpacing: {
    marginRight: spacing.lg,
  },
  sectionTitle: {
    marginBottom: spacing.md,
  },
  card: {
    marginBottom: spacing.lg,
  },
  cardHeader: {
    marginBottom: spacing.sm,
  },
  cardMeta: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: spacing.md,
  },
  ratingRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  ratingButton: {
    flexGrow: 1,
    marginRight: spacing.sm,
    marginBottom: spacing.sm,
  },
  separator: {
    height: spacing.lg,
  },
  emptyState: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 24
  },
  profileCopy: {
    textAlign: 'center',
    marginBottom: spacing.lg
  },
  signOutButton: {
    minWidth: 160
  }
});
