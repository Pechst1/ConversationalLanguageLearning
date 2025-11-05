import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import {
  View,
  StyleSheet,
  FlatList,
  RefreshControl,
  ActivityIndicator,
  ScrollView,
} from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
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

function resolveTranslation(card: AnkiWordProgress) {
  if (card.direction === 'fr_to_de') {
    return card.german_translation || card.english_translation || '';
  }
  if (card.direction === 'de_to_fr') {
    return card.french_translation || card.english_translation || '';
  }
  return card.english_translation || card.french_translation || card.german_translation || '';
}

function formatDueDate(value?: string | null) {
  if (!value) {
    return 'Soon';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return 'Soon';
  }
  return `${date.toLocaleDateString()} · ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
}

const DueCardItem: React.FC<{
  card: AnkiWordProgress;
  onReview: (rating: number) => Promise<void>;
  isReviewing: boolean;
}> = ({ card, onReview, isReviewing }) => {
  return (
    <Card style={styles.card}>
      <View style={styles.cardHeader}>
        <Text variant="title" emphasis="bold">
          {card.word}
        </Text>
        <Text color="textSecondary">{resolveTranslation(card)}</Text>
      </View>
      <View style={styles.cardMeta}>
        <Text variant="caption" color="textSecondary">
          Scheduler · {card.scheduler?.toUpperCase() || 'ANKI'}
        </Text>
        <Text variant="caption" color="textSecondary">
          Due · {formatDueDate(card.due_at ?? card.next_review)}
        </Text>
      </View>
      <View style={styles.ratingRow}>
        {ratingOptions.map(({ label, rating }) => (
          <Button
            key={label}
            label={label}
            variant={rating >= 2 ? 'primary' : 'secondary'}
            onPress={() => {
              void onReview(rating);
            }}
            disabled={isReviewing}
            style={styles.ratingButton}
          />
        ))}
      </View>
    </Card>
  );
};

const LearnScreen: React.FC = () => {
  const {
    profile,
    ankiSummary,
    dueAnkiCards,
    isLoading,
    isSyncing,
    error,
    refresh,
    submitAnkiReview,
    clearError,
  } = useLearnerContext();
  const [refreshing, setRefreshing] = React.useState(false);
  const [reviewingId, setReviewingId] = React.useState<number | null>(null);
  const [localError, setLocalError] = React.useState<string | null>(null);

  React.useEffect(() => {
    setLocalError(error);
  }, [error]);

  const handleRefresh = React.useCallback(async () => {
    setRefreshing(true);
    try {
      await refresh();
      setLocalError(null);
    } finally {
      setRefreshing(false);
    }
  }, [refresh]);

  useFocusEffect(
    React.useCallback(() => {
      let isMounted = true;
      const sync = async () => {
        try {
          await refresh({ background: true });
        } catch (err) {
          if (isMounted) {
            console.warn('Background sync failed', err);
          }
        }
      };

      void sync();
      const intervalId = setInterval(sync, 60_000);
      return () => {
        isMounted = false;
        clearInterval(intervalId);
      };
    }, [refresh])
  );

  const handleReview = React.useCallback(
    async (card: AnkiWordProgress, rating: number) => {
      try {
        setReviewingId(card.word_id);
        await submitAnkiReview(card.word_id, rating);
        setLocalError(null);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Could not submit review';
        setLocalError(message);
      } finally {
        setReviewingId(null);
      }
    },
    [submitAnkiReview]
  );

  const displayedCards = React.useMemo(() => dueAnkiCards.slice(0, 50), [dueAnkiCards]);

  return (
    <View style={styles.screen}>
      {localError ? (
        <Card style={styles.errorCard}>
          <Text color="error" style={styles.errorText}>
            {localError}
          </Text>
          <Button label="Dismiss" variant="ghost" onPress={() => { clearError(); setLocalError(null); }} />
        </Card>
      ) : null}
      <FlatList
        data={displayedCards}
        keyExtractor={(item) => `${item.word_id}`}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing || isSyncing} onRefresh={handleRefresh} tintColor={colors.primary} />
        }
        ListHeaderComponent={
          <View style={styles.header}>
            <Text variant="headline" emphasis="bold" style={styles.headerTitle}>
              {profile?.full_name ? `Bonjour, ${profile.full_name.split(' ')[0]}!` : 'Ready to review?'}
            </Text>
            <Text color="textSecondary" style={styles.headerSubtitle}>
              {ankiSummary
                ? `You have ${ankiSummary.due_today} cards due today across ${ankiSummary.total_cards} total.`
                : 'Check in with your cards to keep momentum.'}
            </Text>
            {ankiSummary ? (
              <View style={styles.summaryRow}>
                {[
                  { label: 'Due today', value: ankiSummary.due_today },
                  { label: 'Total cards', value: ankiSummary.total_cards },
                ].map((stat, index, array) => (
                  <Card
                    key={stat.label}
                    style={[styles.summaryCard, index < array.length - 1 ? styles.summaryCardSpacing : null]}
                  >
                    <Text variant="caption" color="textSecondary">
                      {stat.label}
                    </Text>
                    <Text variant="title" emphasis="bold">
                      {stat.value}
                    </Text>
                  </Card>
                ))}
              </View>
            ) : null}
            <Text variant="subtitle" emphasis="medium" style={styles.sectionTitle}>
              Due cards
            </Text>
          </View>
        }
        ListEmptyComponent={
          isLoading ? (
            <View style={styles.emptyState}>
              <ActivityIndicator color={colors.primary} />
              <Text color="textSecondary" style={styles.emptyText}>
                Loading your study data…
              </Text>
            </View>
          ) : (
            <View style={styles.emptyState}>
              <Ionicons name="checkmark-circle" size={48} color={colors.primary} />
              <Text variant="title" emphasis="bold" style={styles.emptyTitle}>
                All caught up!
              </Text>
              <Text color="textSecondary" style={styles.emptyText}>
                No cards are due right now. Check back later or import new decks.
              </Text>
            </View>
          )
        }
        renderItem={({ item }) => (
          <DueCardItem
            card={item}
            onReview={(rating) => handleReview(item, rating)}
            isReviewing={reviewingId === item.word_id}
          />
        )}
        ItemSeparatorComponent={() => <View style={styles.separator} />}
      />
    </View>
  );
};

const ProfileScreen: React.FC<{ onSignOut: () => void }> = ({ onSignOut }) => {
  const { profile, ankiSummary, reviewQueue, lastSyncedAt, isSyncing, refresh } = useLearnerContext();
  const [refreshing, setRefreshing] = React.useState(false);

  const queueSummary = React.useMemo(() => {
    const now = Date.now();
    return reviewQueue.reduce(
      (acc, item) => {
        acc.total += 1;
        if (item.is_new) {
          acc.new += 1;
        }
        const dueDate = item.next_review ? Date.parse(item.next_review) : null;
        if (dueDate !== null && !Number.isNaN(dueDate) && dueDate <= now) {
          acc.due += 1;
        }
        return acc;
      },
      { total: 0, new: 0, due: 0 }
    );
  }, [reviewQueue]);

  const handleRefresh = React.useCallback(async () => {
    setRefreshing(true);
    try {
      await refresh();
    } finally {
      setRefreshing(false);
    }
  }, [refresh]);

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.profileContent}
      refreshControl={
        <RefreshControl
          refreshing={refreshing || isSyncing}
          onRefresh={handleRefresh}
          tintColor={colors.primary}
        />
      }
    >
      <Card style={styles.card}>
        <Text variant="headline" emphasis="bold">
          {profile?.full_name || 'Learner profile'}
        </Text>
        <Text color="textSecondary">{profile?.email}</Text>
        <View style={styles.profileRow}>
          <View style={[styles.profileColumn, styles.profileColumnSpacing]}>
            <Text variant="caption" color="textSecondary">
              Target language
            </Text>
            <Text variant="subtitle" emphasis="medium">
              {profile?.target_language?.toUpperCase() || '—'}
            </Text>
          </View>
          <View style={[styles.profileColumn, styles.profileColumnSpacing]}>
            <Text variant="caption" color="textSecondary">
              Level
            </Text>
            <Text variant="subtitle" emphasis="medium">
              {profile?.level ?? '—'}
            </Text>
          </View>
          <View style={styles.profileColumn}>
            <Text variant="caption" color="textSecondary">
              Streak
            </Text>
            <Text variant="subtitle" emphasis="medium">
              {profile?.current_streak ?? 0} days
            </Text>
          </View>
        </View>
      </Card>

      {ankiSummary ? (
        <Card style={styles.card}>
          <Text variant="title" emphasis="bold" style={styles.sectionTitle}>
            Anki summary
          </Text>
          <View style={styles.summaryRow}>
            {[
              { label: 'Due today', value: ankiSummary.due_today },
              { label: 'Total cards', value: ankiSummary.total_cards },
            ].map((stat, index, array) => (
              <Card
                key={stat.label}
                style={[styles.summaryCard, index < array.length - 1 ? styles.summaryCardSpacing : null]}
              >
                <Text variant="caption" color="textSecondary">
                  {stat.label}
                </Text>
                <Text variant="title" emphasis="bold">
                  {stat.value}
                </Text>
              </Card>
            ))}
          </View>
          <View style={styles.stageChips}>
            {Object.entries(ankiSummary.stage_totals).map(([stage, count]) => (
              <View key={stage} style={styles.stageChip}>
                <Text variant="caption" color="textSecondary">
                  {stage.replace(/_/g, ' ')}
                </Text>
                <Text variant="body" emphasis="bold">
                  {count}
                </Text>
              </View>
            ))}
          </View>
          <View style={styles.directionList}>
            {Object.entries(ankiSummary.directions).map(([direction, stats], index) => (
              <View
                key={direction}
                style={[styles.directionRow, index === 0 ? null : styles.directionRowSpacing]}
              >
                <Text variant="subtitle" emphasis="medium">
                  {direction.replace(/_/g, ' → ')}
                </Text>
                <Text color="textSecondary">
                  {stats.due_today} due / {stats.total} total
                </Text>
              </View>
            ))}
          </View>
        </Card>
      ) : null}

      <Card style={styles.card}>
        <Text variant="title" emphasis="bold" style={styles.sectionTitle}>
          Practice queue
        </Text>
        <Text color="textSecondary" style={styles.profileSubtitle}>
          {queueSummary.total} cards loaded · {queueSummary.due} due soon · {queueSummary.new} new
        </Text>
      </Card>

      <Button label="Sign out" variant="secondary" onPress={onSignOut} style={styles.signOutButton} />

      <Text variant="caption" color="textSecondary" style={styles.syncInfo}>
        Last synced {lastSyncedAt ? new Date(lastSyncedAt).toLocaleString() : 'just now'}
      </Text>
    </ScrollView>
  );
};

const HomeStackNavigator: React.FC = () => (
  <HomeStack.Navigator>
    <HomeStack.Screen name="Home" options={{ title: 'Reviews' }}>
      {() => <LearnScreen />}
    </HomeStack.Screen>
  </HomeStack.Navigator>
);

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
    paddingVertical: spacing.xl,
  },
  emptyTitle: {
    textAlign: 'center',
    marginTop: spacing.md,
  },
  emptyText: {
    textAlign: 'center',
    paddingHorizontal: spacing.xl,
    marginTop: spacing.sm,
  },
  errorCard: {
    marginHorizontal: spacing.lg,
    marginTop: spacing.lg,
  },
  errorText: {
    marginBottom: spacing.sm,
  },
  profileContent: {
    padding: spacing.lg,
    paddingBottom: spacing.xxl,
  },
  profileRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: spacing.lg,
  },
  profileColumn: {
    flex: 1,
  },
  profileColumnSpacing: {
    marginRight: spacing.lg,
  },
  profileSubtitle: {
    marginTop: spacing.sm,
  },
  stageChips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: spacing.md,
  },
  stageChip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: 999,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    marginRight: spacing.sm,
    marginBottom: spacing.sm,
  },
  directionList: {
    marginTop: spacing.lg,
  },
  directionRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  directionRowSpacing: {
    marginTop: spacing.sm,
  },
  signOutButton: {
    marginTop: spacing.lg,
  },
  syncInfo: {
    marginTop: spacing.sm,
    textAlign: 'center',
  },
});
